import asyncio as aio
import logging
import pickle
import random
from ndn.app import NDNApp
from ndn.encoding import Name, Component

from . import ReadHandle, CommandHandle
from src.concurrent_fetcher import concurrent_fetcher
from src.storage import Storage
from src.command.repo_command_response_pb2 import RepoCommandResponseMessage


class WriteCommandHandle(CommandHandle):
    """
    WriteCommandHandle processes insert command interests, and fetches corresponding data to
    store them into the database.
    TODO: Add validator
    """
    def __init__(self, app: NDNApp, storage: Storage, read_handle: ReadHandle):
        """
        Write handle need to keep a reference to write handle to register new prefixes.
        """
        super(WriteCommandHandle, self).__init__(app, storage)
        self.m_read_handle = read_handle

    def listen(self, name):
        """
        Register routes for command interests.
        This function needs to be called explicitly after initialization.
        """
        name_to_reg = name[:]
        name_to_reg.append('insert')
        self.app.route(name_to_reg)(self._on_insert_interest)

        name_to_reg = name[:]
        name_to_reg.append('insert check')
        self.app.route(name_to_reg)(self.on_check_interest)

    def _on_insert_interest(self, int_name, _int_param, _app_param):
        aio.create_task(self._process_insert(int_name, _int_param, _app_param))

    async def _process_insert(self, int_name, _int_param, _app_param):
        """
        Process segmented insertion command.
        Return to client with status code 100 immediately, and then start data fetching process.
        TODO: When to start listening for interest?
        """
        try:
            cmd_param = self.decode_cmd_param_blob(int_name)
        except RuntimeError as exc:
            logging.info('Parameter interest blob decode failed')
            # TODO: return response
            return

        start_block_id = cmd_param.repo_command_parameter.start_block_id
        end_block_id = cmd_param.repo_command_parameter.end_block_id
        name = []
        for compo in cmd_param.repo_command_parameter.name.component:
            name.append(Component.from_bytes(compo))

        logging.info('Write handle processing insert command: {}, {}, {}'
                     .format(name, start_block_id, end_block_id))

        # Reply to client with status code 100
        process_id = random.randint(0, 0x7fffffff)
        self.m_processes[process_id] = RepoCommandResponseMessage()
        self.m_processes[process_id].repo_command_response.status_code = 100
        self.m_processes[process_id].repo_command_response.process_id = process_id
        self.m_processes[process_id].repo_command_response.insert_num = 0
        self.reply_to_cmd(int_name, self.m_processes[process_id])

        # Start data fetching process
        self.m_processes[process_id].repo_command_response.status_code = 300
        semaphore = aio.Semaphore(1)
        block_id = start_block_id
        async for content in concurrent_fetcher(self.app, name, start_block_id, end_block_id, semaphore):
            data_name = name[:]
            data_name.append(str(block_id))
            self.storage.put(Name.to_str(data_name), pickle.dumps(content.tobytes()))
            assert block_id <= end_block_id
            block_id += 1

        # Insert is successful if all packets are retrieved, or if end_block_id is not set
        insert_num = block_id - start_block_id
        if end_block_id is None or block_id == end_block_id + 1:
            self.m_processes[process_id].repo_command_response.status_code = 200
            logging.info('Segment insertion success, {} items inserted'.format(insert_num))
        else:
            self.m_processes[process_id].repo_command_response.status_code = 400
            logging.info('Segment insertion failure, {} items inserted'.format(insert_num))
        self.m_processes[process_id].repo_command_response.insert_num = insert_num

        # Let read handle listen for this prefix
        existing = CommandHandle.update_prefixes_in_storage(self.storage, Name.to_str(name))
        if not existing:
            # TODO
            # self.m_read_handle.listen(name)
            pass

        # Delete process state after some time
        await self.delete_process(process_id)