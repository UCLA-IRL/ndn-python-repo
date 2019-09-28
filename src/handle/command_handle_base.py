import asyncio
import os
import sys
import logging
from typing import Optional, Callable, Union
from pyndn import Blob, Face, Name, Data, Interest, NetworkNack
from pyndn.security import KeyChain
from pyndn.encoding import ProtobufTlv
from src.storage import Storage
from src.command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from src.command.repo_command_response_pb2 import RepoCommandResponseMessage
from src.command.repo_storage_format_pb2 import PrefixesInStorage


class CommandHandle(object):
    """
    Interface for command interest handles
    TODO: implement insertion check command
    """
    def __init__(self, face: Face, keychain: KeyChain, storage: Storage):
        self.face = face
        self.keychain = keychain
        self.storage = storage
        self.m_processes = dict()

    def listen(self, name: Name):
        raise NotImplementedError

    def on_check_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        logging.info('on_check_interest(): {}'.format(str(interest.getName())))
        response = None
        try:
            parameter = self.decode_cmd_param_blob(interest)
        except RuntimeError as exc:
            response = RepoCommandResponseMessage()
            response.status_code = 403
        process_id = parameter.repo_command_parameter.process_id

        if process_id not in self.m_processes:
            response = RepoCommandResponseMessage()
            response.repo_command_response.status_code = 404

        if response is not None:
            self.reply_to_cmd(interest, response)
        else:
            self.reply_to_cmd(interest, self.m_processes[process_id])

    @staticmethod
    def update_prefixes_in_storage(storage: Storage, prefix: str) -> bool:
        """
        Add a new prefix into database
        return whether the prefix has been registered before
        """
        prefixes_msg = PrefixesInStorage()
        ret = storage.get("prefixes")
        if ret:
            prefixes_msg.ParseFromString(ret)
        for prefix_item in prefixes_msg.prefixes:
            if prefix_item.name == prefix or prefix.startswith(prefix_item.name):
                return True
        new_prefix = prefixes_msg.prefixes.add()
        new_prefix.name = prefix
        storage.put("prefixes", prefixes_msg.SerializeToString())
        logging.info("add a new prefix into the database")
        return False

    def reply_to_cmd(self, interest: Interest, response: RepoCommandResponseMessage):
        """
        Reply to a command interest
        """
        logging.info('Reply to command: {}'.format(interest.getName()))

        response_blob = ProtobufTlv.encode(response)
        data = Data(interest.getName())
        data.metaInfo.freshnessPeriod = 1000
        data.setContent(response_blob)

        self.keychain.sign(data)
        self.face.putData(data)

    @staticmethod
    def decode_cmd_param_blob(interest: Interest) -> RepoCommandParameterMessage:
        """
        Decode the command interest and return a RepoCommandParameterMessage object.
        Command interests have the format of:
        /<routable_repo_prefix>/insert/<cmd_param_blob>/<timestamp>/<random-value>/<SignatureInfo>/<SignatureValue>
        Throw RuntimeError on decoding failure.
        """
        parameter = RepoCommandParameterMessage()
        param_blob = interest.getName()[-5].getValue()

        try:
            ProtobufTlv.decode(parameter, param_blob)
        except RuntimeError as exc:
            raise exc
        return parameter
    
    async def delete_process(self, process_id: int):
        """
        Remove process state after some delay
        TODO: Remove hard-coded duration
        """
        await asyncio.sleep(60)
        if process_id in self.m_processes:
            del self.m_processes[process_id]