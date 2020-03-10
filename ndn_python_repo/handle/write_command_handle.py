import asyncio as aio
import logging
import random
from ndn.app import NDNApp
from ndn.encoding import Name, DecodeError, ndn_format_0_3
from ndn.types import InterestNack, InterestTimeout

from . import ReadHandle, CommandHandle
from ..command.repo_commands import RepoCommandResponse
from ..concurrent_fetcher import concurrent_fetcher
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

    def listen(self, prefix):
        """
        Register routes for command interests.
        This function needs to be called explicitly after initialization.
        :param perfix: NonStrictName. The name prefix to listen on.
        """
        # remember the prefix to check against the namespace of incoming data
        self.prefix = prefix

        prefix_to_reg = prefix[:]
        prefix_to_reg.append('insert')
        self.app.route(prefix_to_reg)(self._on_insert_interest)

        prefix_to_reg = prefix[:]
        prefix_to_reg.append('insert check')
        self.app.route(prefix_to_reg)(self.on_check_interest)

    def _on_insert_interest(self, int_name, _int_param, _app_param):
        aio.get_event_loop().create_task(self._process_insert(int_name, _int_param, _app_param))

    async def _process_insert(self, int_name, _int_param, _app_param):
        """
        Process segmented insertion command.
        Return to client with status code 100 immediately, and then start data fetching process.
        """
        try:
            cmd_param = self.decode_cmd_param_bytes(int_name)
            if cmd_param.name == None:
                raise DecodeError()
        except (DecodeError, IndexError) as exc:
            logging.warning('Parameter interest blob decoding failed')
            self.reply_with_status(int_name, 403)
            return

        name = cmd_param.name
        start_block_id = cmd_param.start_block_id
        end_block_id = cmd_param.end_block_id

        logging.info(f'Write handle processing insert command: {name}, {start_block_id}, {end_block_id}')
        
        # rejects any data that overlaps with repo's own namespace
        if Name.is_prefix(self.prefix, name) or Name.is_prefix(name, self.prefix):
            logging.warning('Inserted data name overlaps with repo prefix')
            self.reply_with_status(int_name, 401)
            return 
        elif self.is_valid_param(cmd_param) == False:
            logging.warning('Insert command malformed: only end_block_id is specified')
            self.reply_with_status(int_name, 403)
            return

        # Reply to client with status code 100
        process_id = random.randint(0, 0x7fffffff)
        self.m_processes[process_id] = RepoCommandResponse()
        self.m_processes[process_id].status_code = 100
        self.m_processes[process_id].process_id = process_id
        self.m_processes[process_id].insert_num = 0
        self.reply_with_response(int_name, self.m_processes[process_id])

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

        # Let read handle listen for this prefix
        existing = CommandHandle.add_prefixes_in_storage(self.storage, name)
        if not existing:
            self.m_read_handle.listen(name)

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
        # first get the data name, then use the name to get the entire packet
        try:
            data_name, _, _ = await self.app.express_interest(
                name, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
            data_bytes = self.app.get_original_packet_value(data_name)
        except InterestNack as e:
            logging.info(f'Nacked with reason={e.reason}')
            return 0
        except InterestTimeout:
            logging.info(f'Timeout')
            return 0
        self.storage.put(Name.to_str(data_name), data_bytes)
        print('Receive single interest')
        return 1

    async def fetch_segmented_data(self, name, start_block_id: int, end_block_id: Optional[int]):
        """
        Fetch segmented Data packets.
        :param name: NonStrictName.
        :return: Number of data packets fetched.
        """
        semaphore = aio.Semaphore(10)
        block_id = start_block_id
        async for data_bytes in concurrent_fetcher(self.app, name, start_block_id, end_block_id, semaphore):
            # Obtain data name by parsing data
            (data_name, _, _, _) = ndn_format_0_3.parse_data(data_bytes, with_tl=False)
            self.storage.put(Name.to_str(data_name), data_bytes)
            assert block_id <= end_block_id
            block_id += 1
        insert_num = block_id - start_block_id
        return insert_num