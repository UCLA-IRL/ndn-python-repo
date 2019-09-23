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
    TODO: add validator
    """
    def listen(self, name: Name):
        """
        Start listening for command interests.
        This function needs to be called explicitly after initialization.
        TODO
        """
        self.face.setInterestFilter(Name(name).append("delete"), self.on_interest)

    def on_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        event_loop = asyncio.get_event_loop()
        event_loop.create_task(self.process_segmented_insert_command(interest))