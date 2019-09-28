import asyncio
import logging
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
    TODO: Is it necessary to support delete check command? If so, given current DB API doesn't
    support async ops, the check command won't be possible to return any "300" status.
    """
    def listen(self, name: Name):
        """
        Start listening for command interests.
        This function needs to be called explicitly after initialization.
        """
        self.face.setInterestFilter(Name(name).append("delete"), self.on_delete_interest)

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
                     .format(name, start_block_id, end_block_id))
        
        # Perform delete
        delete_num = 0
        for idx in range(start_block_id, end_block_id + 1):
            key = str(Name(name).append(str(idx)))
            if self.storage.exists(key):
                self.storage.remove(key)
                delete_num += 1
        
        # Construct response
        response = RepoCommandResponseMessage()
        response.repo_command_response.status_code = 200
        response.repo_command_response.delete_num = delete_num
        self.reply_to_cmd(interest, response)
