"""
    NDN Repo putfile client.

    @Author jonnykong@cs.ucla.edu
            susmit@cs.colostate.edu
    @Date   2019-10-18
"""

import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import asyncio as aio
import logging
import multiprocessing
from ndn.app import NDNApp
from ndn.encoding import Name, Component, DecodeError
from ndn.types import InterestNack, InterestTimeout
from .command_checker import CommandChecker
from ..command.repo_commands import RepoCommandParameter, RepoCommandResponse
from ndn.security import KeychainDigest
import platform
from typing import List


app_create_packets = NDNApp()   # used for _create_packets only
def _create_packets(name, content, freshness_period, final_block_id):
    """
    Worker for parallelize prepare_data().
    This function has to be defined at the top level, so that it can be pickled and used
    by multiprocessing.
    """
    packet = app_create_packets.prepare_data(name, content,
                                             freshness_period=freshness_period,
                                             final_block_id=final_block_id)
    return bytes(packet)


class PutfileClient(object):
    
    def __init__(self, app: NDNApp, repo_name):
        """
        :param app: NDNApp
        :param repo_name: NonStrictName. Routable name to remote repo.
        """
        self.app = app
        self.repo_name = repo_name
        self.encoded_packets = []

        # https://bugs.python.org/issue35219
        if platform.system() == 'Darwin':
            os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'

    def _prepare_data(self, file_path: str, name_at_repo, segment_size: int, freshness_period: int,
                      cpu_count: int):
        """
        Shard file into data packets.
        :param file_path: Local FS path to file to insert
        :param name_at_repo: Name used to store file at repo
        :return: List of encoded packets
        """
        if not os.path.exists(file_path):
            logging.error(f'file {file_path} does not exist')
            return 0
        with open(file_path, 'rb') as binary_file:
            b_array = bytearray(binary_file.read())
        if len(b_array) == 0:
            logging.warning("File is empty")
            return 0
        
        # use multiple threads to speed up creating TLV
        seg_cnt = (len(b_array) + segment_size - 1) // segment_size
        final_block_id = Component.from_segment(seg_cnt - 1)
        packet_params = [[
            name_at_repo + [Component.from_segment(seq)],
            b_array[seq * segment_size : (seq + 1) * segment_size],
            freshness_period,
            final_block_id,
        ] for seq in range(seg_cnt)]
        
        with multiprocessing.Pool(processes=cpu_count) as p:
            self.encoded_packets = p.starmap(_create_packets, packet_params)

    def _on_interest(self, int_name, _int_param, _app_param):
        # use segment number to index into the encoded packets array
        logging.info(f'On interest: {Name.to_str(int_name)}')
        seq = Component.to_number(int_name[-1])
        if seq >= 0 and seq < len(self.encoded_packets):
            self.app.put_raw_packet(self.encoded_packets[seq])
            logging.info(f'Serve data: {Name.to_str(int_name)}')
        else:
            logging.info(f'Data does not exist: {Name.to_str(int_name)}')

    async def insert_file(self, file_path: str, name_at_repo, segment_size: int,
                          freshness_period: int, cpu_count: int):
        """
        Insert a file to remote repo.
        :param file_path: Local FS path to file to insert
        :param name_at_repo: Name used to store file at repo
        :param segment_size: Max size of data packets.
        :param freshness_period: Freshnes of data packets.
        :param cpu_count: Cores used for converting file to TLV format.
        """
        self._prepare_data(file_path, name_at_repo, segment_size, freshness_period, cpu_count)
        num_packets = len(self.encoded_packets)
        if num_packets == 0:
            return

        # Register prefix for responding interests from repo
        await self.app.register(name_at_repo, self._on_interest)

        cmd_param = RepoCommandParameter()
        cmd_param.name = name_at_repo
        cmd_param.start_block_id = 0
        cmd_param.end_block_id = num_packets - 1
        cmd_param_bytes = cmd_param.encode()

        # Send cmd interest to repo
        name = self.repo_name[:]
        name.append('insert')
        name.append(Component.from_bytes(cmd_param_bytes))

        try:
            logging.info(f'Expressing interest: {Name.to_str(name)}')
            data_name, meta_info, content = await self.app.express_interest(
                name, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
            logging.info(f'Received data name: {Name.to_str(data_name)}')
        except InterestNack as e:
            logging.warning(f'Nacked with reason: {e.reason}')
            return
        except InterestTimeout:
            logging.warning(f'Timeout')
            return

        # Parse response from repo
        try:
            cmd_response = RepoCommandResponse.parse(content)
        except DecodeError as exc:
            logging.warning('Response blob decoding failed')
            return
        process_id = cmd_response.process_id
        status_code = cmd_response.status_code
        
        if status_code == 401:
            logging.info('This insertion command or insertion check command is invalidated')
            return
        if status_code == 403:
            logging.warning('Malformed command')
            return
        logging.info(f'cmd_response process {process_id} accepted: status code {status_code}')

        # Send insert check interest to wait until insert process completes
        checker = CommandChecker(self.app)
        while True:
            response = await checker.check_insert(self.repo_name, process_id)
            if response is None:
                logging.info(f'Response code is None')
                await aio.sleep(1)
            elif response.status_code == 300:
                logging.info(f'Response code is {response.status_code}')
                await aio.sleep(1)
            elif response.status_code == 200:
                logging.info('Insert process {} status: {}, insert_num: {}'
                             .format(process_id,
                                     response.status_code,
                                     response.insert_num))
                break
            else:
                # Shouldn't get here
                assert False, f'Received unrecognized status code {response.status_code}'