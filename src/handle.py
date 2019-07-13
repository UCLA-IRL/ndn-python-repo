import os
import sys
import logging
from pyndn import Face, Name, Data, Interest
from pyndn.security import KeyChain
from pyndn.encoding import ProtobufTlv
from storage import Storage
from command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from command.repo_command_response_pb2 import RepoCommandResponseMessage

class Handle(object):
    """
    Interface for handle functionalities
    """
    def listen(self, name: Name):
        raise NotImplementedError


class WriteHandle(Handle):
    """
    WriteHandle processes command interests, and fetches corresponding data to
    store them into the database.
    TODO: Add validator
    """

    def __init__(self, face: Face, keychain: KeyChain, storage: Storage):
        self.face = face
        self.keychain = keychain
        self.storage = storage

    def listen(self, name: Name):
        """
        Start listening for command interests.
        This function needs to be called explicitly before being used.
        """

        self.face.setInterestFilter(Name(name).append("insert"), self.on_interest)
        logging.info("Set interest filter: {}".format(Name(name).append("insert")))

    def on_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        """
        On receiving command interest for data insertion
        """
        logging.info("WriteHandle on_interest(): {}".format(interest.name.toUri()))

        # TODO: On segmented interest
        self.on_single_insert(interest)

    def on_single_insert(self, interest: Interest):
        logging.info("WriteHandle on_single_insert(): {}".format(interest.name.toUri()))
        parameter = RepoCommandParameterMessage()
        try:
            ProtobufTlv.decode(parameter, interest.getApplicationParameters())
        except RuntimeError as exc:
            print('Decode failed', exc)


class ReadHandle(Handle):
    def __init__(self, face: Face, keychain: KeyChain, storage: Storage):
        self.face = face
        self.keychain = keychain
        self.storage = storage

    def listen(self, name: Name):
        """
        Start listening for command interests.
        This function needs to be called explicitly before being used.
        """
        pass


class DeleteHandle(Handle):
    def __init__(self, face: Face, keychain: KeyChain, storage: Storage):
        self.face = face
        self.keychain = keychain
        self.storage = storage

    def listen(self, name: Name):
        """
        Start listening for command interests.
        This function needs to be called explicitly before being used.
        """
        pass

