import asyncio as aio
import logging
import random
import sys
from ndn.app import NDNApp
from ndn.encoding import Name, DecodeError
from . import ReadHandle, CommandHandle
from ..storage import Storage
from ..command.repo_commands import RepoCommandResponse


class DeleteCommandHandle(CommandHandle):
    """
    DeleteCommandHandle processes delete command handles, and deletes corresponding data stored
    in the database.
    TODO: Add validator
    """
    def __init__(self, app: NDNApp, storage: Storage, read_handle: ReadHandle):
        """
        :param app: NDNApp.
        :param storage: Storage.
        :param read_handle: ReadHandle. This param is necessary because DeleteCommandHandle need to
            unregister prefixes.
        """
        super(DeleteCommandHandle, self).__init__(app, storage)
        self.m_read_handle = read_handle

    def listen(self, prefix: Name):
        """
        Register routes for command interests.
        This function needs to be called explicitly after initialization.
        :param name: NonStrictName. The name prefix to listen on.
        """
        prefix_to_reg = prefix[:]
        prefix_to_reg.append('delete')
        self.app.route(prefix_to_reg)(self._on_delete_interest)

        prefix_to_reg = prefix[:]
        prefix_to_reg.append('delete check')
        self.app.route(prefix_to_reg)(self.on_check_interest)

    def _on_delete_interest(self, int_name, _int_param, _app_param):
        aio.get_event_loop().create_task(self._process_delete(int_name, _int_param, _app_param))
    
    async def _process_delete(self, int_name, _int_param, _app_param):
        """
        Process delete command.
        Return to client with status code 100 immediately, and then start data fetching process.
        # TODO: un-register prefix
        """
        try:
            cmd_param = self.decode_cmd_param_bytes(int_name)
            if cmd_param.name == None:
                raise DecodeError()
        except (DecodeError, IndexError) as exc:
            logging.warning('Parameter interest decoding failed')
            self.reply_with_status(int_name, 403)
            return
        
        name = cmd_param.name
        start_block_id = cmd_param.start_block_id if cmd_param.start_block_id else 0
        end_block_id = cmd_param.end_block_id if cmd_param.end_block_id else sys.maxsize

        logging.info(f'Delete handle processing delete command: {name}, {start_block_id}, {end_block_id}')

        # Reply to client with status code 100
        process_id = random.randint(0, 0x7fffffff)
        self.m_processes[process_id] = RepoCommandResponse()
        self.m_processes[process_id].status_code = 100
        self.m_processes[process_id].process_id = process_id
        self.m_processes[process_id].delete_num = 0
        self.reply_with_response(int_name, self.m_processes[process_id])

        # Un-register prefix
        existing = CommandHandle.remove_prefixes_in_storage(self.storage, name)
        if existing:
            self.m_read_handle.unlisten(name)

        # Perform delete
        self.m_processes[process_id].status_code = 300
        delete_num = await self._perform_storage_delete(name, start_block_id, end_block_id)

        # Delete complete, update process state
        self.m_processes[process_id].status_code = 200
        self.m_processes[process_id].delete_num = delete_num

        # Remove process state after some time
        await self.schedule_delete_process(process_id)

    async def _perform_storage_delete(self, prefix, start_block_id: int, end_block_id: int) -> int:
        """
        Delete data packets between [start_block_id, end_block_id]. If end_block_id is None, delete
        all continuous data packets from start_block_id.
        :param prefix: NonStrictName.
        :param start_block_id: int.
        :param end_block_id: int.
        :return: The number of data items deleted.
        """
        delete_num = 0
        for idx in range(start_block_id, end_block_id + 1):
            key = prefix[:]
            key.append(str(idx))
            key = Name.to_str(key)
            if self.storage.exists(key):
                self.storage.remove(key)
                delete_num += 1
            else:
                # assume sequence numbers are continuous
                break
            # Temporarily release control to make the process non-blocking
            await aio.sleep(0)
        return delete_num