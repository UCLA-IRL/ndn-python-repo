# -----------------------------------------------------------------------------
# NDN Repo putfile client.
#
# @Author jonnykong@cs.ucla.edu
#         susmit@cs.colostate.edu
# @Date   2019-10-18
# -----------------------------------------------------------------------------

import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import asyncio as aio
from .command_checker import CommandChecker
from ..command.repo_commands import RepoCommandParameter, RepoCommandResponse, ForwardingHint,\
    RegisterPrefix, CheckPrefix
from ..utils import PubSub
import logging
import multiprocessing
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName, Component, DecodeError
from ndn.types import InterestNack, InterestTimeout
from ndn.security import KeychainDigest
from ndn.utils import gen_nonce
import os
import platform
from typing import List, Optional


if not os.environ.get('READTHEDOCS'):
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

    def __init__(self, app: NDNApp, prefix: NonStrictName, repo_name: NonStrictName):
        """
        A client to insert files into the repo.

        :param app: NDNApp.
        :param prefix: NonStrictName. The name of this client
        :param repo_name: NonStrictName. Routable name to remote repo.
        """
        self.app = app
        self.prefix = prefix
        self.repo_name = repo_name
        self.encoded_packets = []
        self.pb = PubSub(self.app, self.prefix)

        # https://bugs.python.org/issue35219
        if platform.system() == 'Darwin':
            os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'

    def _prepare_data(self, file_path: str, name_at_repo, segment_size: int, freshness_period: int,
                      cpu_count: int):
        """
        Shard file into data packets.

        :param file_path: Local FS path to file to insert
        :param name_at_repo: Name used to store file at repo
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

    async def insert_file(self, file_path: str, name_at_repo: NonStrictName, segment_size: int,
                          freshness_period: int, cpu_count: int,
                          forwarding_hint: Optional[NonStrictName]=None,
                          register_prefix: Optional[NonStrictName]=None,
                          check_prefix: Optional[NonStrictName]=None) -> int:
        """
        Insert a file to remote repo.

        :param file_path: Local FS path to file to insert.
        :param name_at_repo: NonStrictName. Name used to store file at repo.
        :param segment_size: Max size of data packets.
        :param freshness_period: Freshness of data packets.
        :param cpu_count: Cores used for converting file to TLV format.
        :param forwarding_hint: NonStrictName. The forwarding hint the repo uses when fetching data.
        :param register_prefix: NonStrictName. If repo is configured with ``register_root=False``,\
            it registers ``register_prefix`` after receiving the insertion command.
        :param check_prefix: NonStrictName. The repo will publish process check messages under\
            ``<check_prefix>/check``. It is necessary to specify this value in the param, instead\
            of using a predefined prefix, to make sure the subscriber can register this prefix\
            under the NDN prefix registration security model. If not specified, default value is\
            the client prefix.
        :return: Number of packets inserted.
        """
        self._prepare_data(file_path, name_at_repo, segment_size, freshness_period, cpu_count)
        num_packets = len(self.encoded_packets)
        if num_packets == 0:
            return

        # Register prefix for responding interests from repo
        await self.app.register(name_at_repo, self._on_interest)

        # construct insert cmd msg
        cmd_param = RepoCommandParameter()
        cmd_param.name = name_at_repo
        cmd_param.forwarding_hint = ForwardingHint()
        cmd_param.forwarding_hint.name = forwarding_hint
        cmd_param.start_block_id = 0
        cmd_param.end_block_id = num_packets - 1
        process_id = gen_nonce()
        cmd_param.process_id = process_id
        cmd_param.register_prefix = RegisterPrefix()
        cmd_param.register_prefix.name = register_prefix
        if check_prefix == None:
            check_prefix = self.prefix
        cmd_param.check_prefix = CheckPrefix()
        cmd_param.check_prefix.name = check_prefix
        cmd_param_bytes = cmd_param.encode()

        # publish msg to repo's insert topic
        await self.pb.wait_for_ready()
        self.pb.publish(self.repo_name + ['insert'], cmd_param_bytes)
        logging.info('published an insert msg')

        # wait until finish so that repo can finish fetching the data
        return await self._wait_for_finish(check_prefix, process_id)

    async def _wait_for_finish(self, check_prefix: NonStrictName, process_id: int) -> int:
        """
        Wait until process `process_id` completes by sending check interests.

        :param check_prefix: NonStrictName. The prefix under which the check message will be\
            published.
        :param process_id: int. The process id to check.
        :return: number of inserted packets.
        """
        checker = CommandChecker(self.app, self.pb)
        n_retries = 3
        while n_retries > 0:
            response = checker.check(check_prefix, process_id)
            if response is None:
                logging.info(f'Response code is None')
                await aio.sleep(1)
            # might receive 404 if repo has not yet processed insert command msg
            elif response.status_code == 404:
                n_retries -= 1
                await aio.sleep(1)
            elif response.status_code == 300:
                logging.info(f'Response code is {response.status_code}')
                await aio.sleep(1)
            elif response.status_code == 200:
                logging.info('Insert process {} status: {}, insert_num: {}'
                             .format(process_id,
                                     response.status_code,
                                     response.insert_num))
                return response.insert_num
            else:
                # Shouldn't get here
                assert False, f'Received unrecognized status code {response.status_code}'
