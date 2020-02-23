import asyncio as aio
import logging
import random
from ndn.app import NDNApp
from ndn.encoding import Name, DecodeError, ndn_format_0_3

from . import ReadHandle, CommandHandle
from ..concurrent_fetcher import concurrent_fetcher
from ..storage import Storage
from ..command.repo_commands import RepoCommandResponse


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

    def listen(self, name):
        """
        Register routes for command interests.
        This function needs to be called explicitly after initialization.
        :param name: NonStrictName. The name prefix to listen on.
        """
        name_to_reg = name[:]
        name_to_reg.append('insert')
        self.app.route(name_to_reg)(self._on_insert_interest)

        name_to_reg = name[:]
        name_to_reg.append('insert check')
        self.app.route(name_to_reg)(self.on_check_interest)

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
            logging.info('Parameter interest blob decoding failed')
            ret = RepoCommandResponse()
            ret.status_code = 403
            self.reply_to_cmd(int_name, ret)
            return

        name = cmd_param.name
        start_block_id = cmd_param.start_block_id
        end_block_id = cmd_param.end_block_id

        logging.info(f'Write handle processing insert command: {name}, {start_block_id}, {end_block_id}')

        # Reply to client with status code 100
        process_id = random.randint(0, 0x7fffffff)
        self.m_processes[process_id] = RepoCommandResponse()
        self.m_processes[process_id].status_code = 100
        self.m_processes[process_id].process_id = process_id
        self.m_processes[process_id].insert_num = 0
        self.reply_to_cmd(int_name, self.m_processes[process_id])

        # Start data fetching process
        self.m_processes[process_id].status_code = 300
        semaphore = aio.Semaphore(10)
        block_id = start_block_id
        async for data_bytes in concurrent_fetcher(self.app, name, start_block_id, end_block_id, semaphore):
            # Obtain data name by parsing data
            (data_name, _, _, _) = ndn_format_0_3.parse_data(data_bytes, with_tl=False)
            self.storage.put(Name.to_str(data_name), data_bytes)
            assert block_id <= end_block_id
            block_id += 1

        # Insert is successful if all packets are retrieved, or if end_block_id is not set
        insert_num = block_id - start_block_id
        if end_block_id is None or block_id == end_block_id + 1:
            self.m_processes[process_id].status_code = 200
            logging.info('Segment insertion success, {} items inserted'.format(insert_num))
        else:
            self.m_processes[process_id].status_code = 400
            logging.info('Segment insertion failure, {} items inserted'.format(insert_num))
        self.m_processes[process_id].insert_num = insert_num

        # Let read handle listen for this prefix
        existing = CommandHandle.add_prefixes_in_storage(self.storage, name)
        if not existing:
            self.m_read_handle.listen(name)

        # Delete process state after some time
        await self.schedule_delete_process(process_id)
