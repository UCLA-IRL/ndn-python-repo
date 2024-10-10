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
from ..command import RepoCommandParam, ObjParam, EmbName, RepoStatCode
from ..utils import PubSub
import logging
import multiprocessing
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName, Component, Links
import os
import platform
from hashlib import sha256
from typing import Optional


if not os.environ.get('READTHEDOCS'):
    # I don't think global variable is good design
    app_to_create_packet = None   # used for _create_packets only

    def _create_packets(name, content, freshness_period, final_block_id):
        """
        Worker for parallelize prepare_data().
        This function has to be defined at the top level, so that it can be pickled and used
        by multiprocessing.
        """
        # The keychain's sqlite3 connection is not thread-safe. Create a new NDNApp instance for
        # each process, so that each process gets a separate sqlite3 connection
        global app_to_create_packet
        if app_to_create_packet is None:
            app_to_create_packet = NDNApp()

        packet = app_to_create_packet.prepare_data(name, content,
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
        self.repo_name = Name.normalize(repo_name)
        self.encoded_packets = {}
        self.pb = PubSub(self.app, self.prefix)
        self.pb.base_prefix = self.prefix
        self.logger = logging.getLogger(__name__)

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
            self.logger.error(f'file {file_path} does not exist')
            return 0
        with open(file_path, 'rb') as binary_file:
            b_array = bytearray(binary_file.read())
        if len(b_array) == 0:
            self.logger.warning("File is empty")
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

        self.encoded_packets[Name.to_str(name_at_repo)] = []

        with multiprocessing.Pool(processes=cpu_count) as p:
            self.encoded_packets[Name.to_str(name_at_repo)] = p.starmap(_create_packets, packet_params)
        self.logger.info("Prepared {} data for {}".format(seg_cnt, Name.to_str(name_at_repo)))

    def _on_interest(self, int_name, _int_param, _app_param):
        # use segment number to index into the encoded packets array
        self.logger.info(f'On interest: {Name.to_str(int_name)}')
        seq = Component.to_number(int_name[-1])
        name_wo_seq = Name.to_str(int_name[:-1])
        if name_wo_seq in self.encoded_packets and 0 <= seq < len(self.encoded_packets[name_wo_seq]):
            encoded_packets = self.encoded_packets[name_wo_seq]
            self.app.put_raw_packet(encoded_packets[seq])
            self.logger.info(f'Serve data: {Name.to_str(int_name)}')
        else:
            self.logger.info(f'Data does not exist: {Name.to_str(int_name)}')

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
        num_packets = len(self.encoded_packets[Name.to_str(name_at_repo)])
        if num_packets == 0:
            return 0

        # If the uploaded file has the client's name as prefix, set an interest filter
        # for handling corresponding Interests from the repo
        if Name.is_prefix(self.prefix, name_at_repo):
            self.app.set_interest_filter(name_at_repo, self._on_interest)
        else:
            # Otherwise, register the file name as prefix for responding interests from the repo
            self.logger.info(f'Register prefix for file upload: {Name.to_str(name_at_repo)}')
            await self.app.register(name_at_repo, self._on_interest)

        # construct insert cmd msg
        cmd_param = RepoCommandParam()
        cmd_obj = ObjParam()
        cmd_param.objs = [cmd_obj]
        cmd_obj.name = name_at_repo
        if forwarding_hint is not None:
            cmd_obj.forwarding_hint = Links()
            cmd_obj.forwarding_hint.names = [forwarding_hint]
        else:
            cmd_obj.forwarding_hint = None
        cmd_obj.start_block_id = 0
        cmd_obj.end_block_id = num_packets - 1
        cmd_obj.register_prefix = EmbName()
        cmd_obj.register_prefix.name = register_prefix

        cmd_param_bytes = bytes(cmd_param.encode())
        request_no = sha256(cmd_param_bytes).digest()

        # publish msg to repo's insert topic
        await self.pb.wait_for_ready()
        is_success = await self.pb.publish(self.repo_name + Name.from_str('insert'), cmd_param_bytes)
        if is_success:
            self.logger.info('Published an insert msg and was acknowledged by a subscriber')
        else:
            self.logger.info('Published an insert msg but was not acknowledged by a subscriber')

        # wait until finish so that repo can finish fetching the data
        insert_num = 0
        if is_success:
            insert_num = await self._wait_for_finish(check_prefix, request_no)
        return insert_num

    async def _wait_for_finish(self, check_prefix: NonStrictName, request_no: bytes) -> int:
        """
        Wait until process `process_id` completes by sending check interests.

        :param check_prefix: NonStrictName. The prefix under which the check message will be\
            published.
        :param request_no: bytes. The request number to check.
        :return: int number of inserted packets.
        """
        # fixme: why is check_prefix not used?
        checker = CommandChecker(self.app)
        n_retries = 5
        while n_retries > 0:
            response = await checker.check_insert(self.repo_name, request_no)
            if response is None:
                self.logger.info(f'No response')
                n_retries -= 1
                await aio.sleep(1)
            # might receive 404 if repo has not yet processed insert command msg
            elif response.status_code == RepoStatCode.NOT_FOUND:
                n_retries -= 1
                await aio.sleep(1)
            elif response.status_code == RepoStatCode.IN_PROGRESS:
                self.logger.info(f'Insertion {request_no} in progress')
                await aio.sleep(1)
            elif response.status_code == RepoStatCode.COMPLETED:
                insert_num = 0
                for obj in response.objs:
                    insert_num += obj.insert_num
                self.logger.info(f'Deletion request {request_no} complete, insert_num: {insert_num}')
                return insert_num
            elif response.status_code == RepoStatCode.FAILED:
                self.logger.info(f'Deletion request {request_no} failed')
            else:
                # Shouldn't get here
                self.logger.error(f'Received unrecognized status code {response.status_code}')
