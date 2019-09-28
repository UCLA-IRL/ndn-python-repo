import asyncio
import logging
import random
from typing import Optional, Callable, Union
from pyndn import Blob, Face, Name, Data, Interest, NetworkNack
from pyndn.security import KeyChain
from pyndn.encoding import ProtobufTlv
from . import ReadHandle, CommandHandle
from src.storage import Storage
from src.command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from src.command.repo_command_response_pb2 import RepoCommandResponseMessage
from src.command.repo_storage_format_pb2 import PrefixesInStorage


class DeleteCommandHandle(CommandHandle):
    """
    DeleteCommandHandle processes delete command handles, and deletes corresponding data stored
    in the database.
    TODO: Add validator
    TODO: Current DB API doesn't support async ops, so the check command won't return any "300" status.
    """
    def __init__(self, face: Face, keychain: KeyChain, storage: Storage):
        super(DeleteCommandHandle, self).__init__(face, keychain, storage)

    def listen(self, name: Name):
        """
        Start listening for command interests.
        This function needs to be called explicitly after initialization.
        """
        self.face.setInterestFilter(Name(name).append("delete"), self.on_delete_interest)
        logging.info('Set interest filter: {}'.format(Name(name).append('delete')))
        self.face.setInterestFilter(Name(name).append('delete check'), self.on_check_interest)
        logging.info('Set interest filter: {}'.format(Name(name).append('delete check')))

    def on_delete_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        event_loop = asyncio.get_event_loop()
        event_loop.create_task(self.process_delete(interest))
    
    async def process_delete(self, interest: Interest):
        """
        Process segmented delete command.
        """
        try:
            parameter = self.decode_cmd_param_blob(interest)
        except RuntimeError as exc:
            logging.info('Parameter interest blob decode failed')
            return
        
        name = Name()
        for compo in parameter.repo_command_parameter.name.component:
            name.append(compo)
        start_block_id = parameter.repo_command_parameter.start_block_id
        start_block_id = start_block_id if start_block_id else 0
        end_block_id = parameter.repo_command_parameter.end_block_id

        logging.info('Delete handle processing delete command: {}, {}, {}'
                     .format(str(name), start_block_id, end_block_id))
        
        # Reply to client with status code 100
        process_id = random.randint(0, 0x7fffffff)
        self.m_processes[process_id] = RepoCommandResponseMessage()
        self.m_processes[process_id].repo_command_response.status_code = 100
        self.m_processes[process_id].repo_command_response.process_id = process_id
        self.m_processes[process_id].repo_command_response.delete_num = 0

        self.reply_to_cmd(interest, self.m_processes[process_id])
        
        # Perform delete
        delete_num = self.perform_delete(str(name), start_block_id, end_block_id)
        
        # TODO: because DB ops are blocking, there's no "300" state
        self.m_processes[process_id].repo_command_response.status_code = 200
        self.m_processes[process_id].repo_command_response.delete_num = delete_num
        self.reply_to_cmd(interest, self.m_processes[process_id])

        # Delete process state after some time
        await self.delete_process(process_id)
    
    def perform_delete(self, prefix: str, start_block_id: int, end_block_id: int) -> int:
        """
        Perform DB delete.
        Return the number of data items deleted.
        """
        delete_num = 0
        for idx in range(start_block_id, end_block_id + 1):
            key = str(Name(prefix).append(str(idx)))
            if self.storage.exists(key):
                self.storage.remove(key)
                delete_num += 1
        return delete_num
