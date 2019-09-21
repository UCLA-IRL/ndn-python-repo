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

    def listen(self, name: Name):
        raise NotImplementedError

    def on_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        raise NotImplementedError

    @staticmethod
    def update_prefixes_in_storage(storage: Storage, prefix: str):
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
    def decode_cmd_param_blob(interest: Interest):
        """
        Decode the command interest and return a RepoCommandParameterMessage object.
        Command interests have the format of:
        /<routable_repo_prefix>/insert/<cmd_param_blob>/<timestamp>/<random-value>/<SignatureInfo>/<SignatureValue>
        """
        parameter = RepoCommandParameterMessage()
        param_blob = interest.getName()[-5].getValue()

        try:
            ProtobufTlv.decode(parameter, param_blob)
        except RuntimeError as exc:
            logging.warning('Decode failed', exc)
        return parameter