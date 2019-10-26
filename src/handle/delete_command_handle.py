import asyncio as aio
import logging
import random
from ndn.app import NDNApp
from ndn.encoding import Name, Component
from pyndn.encoding import ProtobufTlv
from . import CommandHandle
from src.storage import Storage
from src.command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from src.command.repo_command_response_pb2 import RepoCommandResponseMessage


class DeleteCommandHandle(CommandHandle):
    """
    DeleteCommandHandle processes delete command handles, and deletes corresponding data stored
    in the database.
    TODO: Add validator
    TODO: Un-register prefixes after delete.
    """
    def __init__(self, app: NDNApp, storage: Storage):
        """
        :param app: NDNApp.
        :param storage: Storage.
        """
        super(DeleteCommandHandle, self).__init__(app, storage)

    def listen(self, name: Name):
        """
        Register routes for command interests.
        This function needs to be called explicitly after initialization.
        :param name: NonStrictName. The name prefix to listen on.
        """
        name_to_reg = name[:]
        name_to_reg.append('delete')
        self.app.route(name_to_reg)(self._on_delete_interest)

        name_to_reg = name[:]
        name_to_reg.append('delete check')
        self.app.route(name_to_reg)(self.on_check_interest)

    def _on_delete_interest(self, int_name, _int_param, _app_param):
        aio.create_task(self._process_delete(int_name, _int_param, _app_param))
    
    async def _process_delete(self, int_name, _int_param, _app_param):
        """
        Process segmented delete command.
        Return to client with status code 100 immediately, and then start data fetching process.
        """
        try:
            cmd_param = self.decode_cmd_param_blob(int_name)
        except RuntimeError as exc:
            logging.info('Parameter interest blob decode failed')
            return

        start_block_id = cmd_param.repo_command_parameter.start_block_id
        end_block_id = cmd_param.repo_command_parameter.end_block_id
        name = []
        for compo in cmd_param.repo_command_parameter.name.component:
            name.append(Component.from_bytes(compo))

        logging.info(f'Delete handle processing delete command: {name}, {start_block_id}, {end_block_id}')

        # Reply to client with status code 100
        process_id = random.randint(0, 0x7fffffff)
        self.m_processes[process_id] = RepoCommandResponseMessage()
        self.m_processes[process_id].repo_command_response.status_code = 100
        self.m_processes[process_id].repo_command_response.process_id = process_id
        self.m_processes[process_id].repo_command_response.insert_num = 0
        self.reply_to_cmd(int_name, self.m_processes[process_id])

        # Perform delete
        self.m_processes[process_id].repo_command_response.status_code = 300
        delete_num = await self._perform_storage_delete(name, start_block_id, end_block_id)

        # Delete complete, update process state
        self.m_processes[process_id].repo_command_response.status_code = 200
        self.m_processes[process_id].repo_command_response.delete_num = delete_num

        # Remove process state after some time
        await self.schedule_delete_process(process_id)

    async def _perform_storage_delete(self, prefix, start_block_id: int, end_block_id: int) -> int:
        """
        Delete items from storage.
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
            print('ABOUT TO DELETE {}'.format(key))
            if self.storage.exists(key):
                self.storage.remove(key)
                delete_num += 1
            # Temporarily release control to make the process non-blocking
            await aio.sleep(0)
        return delete_num