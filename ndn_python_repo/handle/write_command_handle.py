import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, DecodeError
from ndn.types import InterestNack, InterestTimeout

from . import ReadHandle, CommandHandle
from ..command.repo_commands import RepoCommandParameter, RepoCommandResponse
from ..utils import concurrent_fetcher, PubSub
from ..storage import Storage
from typing import Optional


class WriteCommandHandle(CommandHandle):
    """
    WriteCommandHandle processes insert command interests, and fetches corresponding data to
    store them into the database.
    TODO: Add validator
    """
    def __init__(self, app: NDNApp, storage: Storage, read_handle: ReadHandle):
        """
        Write handle need to keep a reference to write handle to register new prefixes.

        :param app: NDNApp.
        :param storage: Storage.
        :param read_handle: ReadHandle. This param is necessary, because WriteCommandHandle need to
            call ReadHandle.listen() to register new prefixes.
        """
        super(WriteCommandHandle, self).__init__(app, storage)
        self.m_read_handle = read_handle
        self.prefix = None

    async def listen(self, prefix):
        """
        Register routes for command interests.
        This function needs to be called explicitly after initialization.

        :param perfix: NonStrictName. The name prefix to listen on.
        """
        self.prefix = prefix

        # subscribe to insert messages
        self.pb = PubSub(self.app, self.prefix)
        await self.pb.wait_for_ready()
        self.pb.subscribe(self.prefix + ['insert'], self._on_insert_msg)

        # listen on insert check interests
        self.app.route(self.prefix + ['insert check'])(self._on_check_interest)

    def _on_insert_msg(self, msg):
        try:
            cmd_param = RepoCommandParameter.parse(msg)
            if cmd_param.name == None:
                raise DecodeError()
        except (DecodeError, IndexError) as exc:
            logging.warning('Parameter interest blob decoding failed')
            return
        aio.ensure_future(self._process_insert(cmd_param))

    async def _process_insert(self, cmd_param: RepoCommandParameter):
        """
        Process segmented insertion command.
        Return to client with status code 100 immediately, and then start data fetching process.
        """
        name = cmd_param.name
        start_block_id = cmd_param.start_block_id
        end_block_id = cmd_param.end_block_id
        process_id = cmd_param.process_id

        logging.info(f'Write handle processing insert command: {name}, {start_block_id}, {end_block_id}')

        # rejects any data that overlaps with repo's own namespace
        if Name.is_prefix(self.prefix, name) or Name.is_prefix(name, self.prefix):
            logging.warning('Inserted data name overlaps with repo prefix')
            return
        elif self.is_valid_param(cmd_param) == False:
            logging.warning('Insert command malformed: only end_block_id is specified')
            return

        # Reply to client with status code 100
        self.m_processes[process_id] = RepoCommandResponse()
        self.m_processes[process_id].status_code = 100
        self.m_processes[process_id].process_id = process_id
        self.m_processes[process_id].insert_num = 0

        # Start data fetching process
        self.m_processes[process_id].status_code = 300
        insert_num = 0
        is_success = False
        if start_block_id != None:
            # Fetch data packets with block ids appended to the end
            insert_num = await self.fetch_segmented_data(name, start_block_id, end_block_id)
            if end_block_id is None or start_block_id + insert_num - 1 == end_block_id:
                is_success = True
        else:
            # Both start_block_id and end_block_id are None, fetch a single data packet
            insert_num = await self.fetch_single_data(name)
            if insert_num == 1:
                is_success = True

        if is_success:
            self.m_processes[process_id].status_code = 200
            logging.info('Insertion success, {} items inserted'.format(insert_num))
        else:
            self.m_processes[process_id].status_code = 400
            logging.info('Insertion failure, {} items inserted'.format(insert_num))
        self.m_processes[process_id].insert_num = insert_num

        # Delete process state after some time
        await self.schedule_delete_process(process_id)

    def is_valid_param(self, cmd_param):
        """
        Validate insert parameter.
        :param cmd_param: RepoCommandParameter.
        :return: Is valid param.
        """
        start_block_id = cmd_param.start_block_id
        end_block_id = cmd_param.end_block_id
        # can't have start_block_id not specified, but end_block_id specified
        if start_block_id == None and end_block_id != None:
            return False
        elif start_block_id != None and end_block_id != None:
            if start_block_id > end_block_id:
                return False

    async def fetch_single_data(self, name):
        """
        Fetch one Data packet.
        :param name: NonStrictName.
        :return:  Number of data packets fetched.
        """
        try:
            data_name, _, _, data_bytes = await self.app.express_interest(
                name, need_raw_packet=True, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
        except InterestNack as e:
            logging.info(f'Nacked with reason={e.reason}')
            return 0
        except InterestTimeout:
            logging.info(f'Timeout')
            return 0
        self.storage.put_data_packet(data_name, data_bytes)
        return 1

    async def fetch_segmented_data(self, name, start_block_id: int, end_block_id: Optional[int]):
        """
        Fetch segmented Data packets.
        :param name: NonStrictName.
        :return: Number of data packets fetched.
        """
        semaphore = aio.Semaphore(10)
        block_id = start_block_id
        async for (data_name, _, _, data_bytes) in concurrent_fetcher(self.app, name, start_block_id, end_block_id, semaphore):
            self.storage.put_data_packet(data_name, data_bytes)
            block_id += 1
        insert_num = block_id - start_block_id
        return insert_num