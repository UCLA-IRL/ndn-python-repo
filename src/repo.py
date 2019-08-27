import os
import sys
import asyncio
import logging
from pyndn import Face, Name, Data, Interest, Blob
from pyndn.security import KeyChain

from storage import Storage
from handle import ReadHandle, CommandHandle
from service_discovery import ServiceDiscovery
from command.repo_storage_format_pb2 import PrefixesInStorage, CommandsInStorage


class Repo(object):
    def __init__(self, repo_common_prefix: Name, repo_unique_prefix: Name, face: Face,
                 keychain: KeyChain, storage: Storage, read_handle: ReadHandle, cmd_handle: CommandHandle):
        """
        Recover from previous context on startup
        """
        self.repo_common_prefix = repo_common_prefix
        self.repo_unique_prefix = repo_unique_prefix
        self.face = face
        self.keychain = keychain
        self.storage = storage
        self.read_handle = read_handle
        self.cmd_handle = cmd_handle
        self.sd = ServiceDiscovery(self.repo_unique_prefix, self.face, self.keychain)
        self.running = True

        self.recover_previous_context()
        self.face.registerPrefix(self.repo_common_prefix, None, self.on_register_failed)
        self.cmd_handle.listen_for_cmd(self.repo_common_prefix)

    def recover_previous_context(self):
        """
        Restore repo to previous context after restart from the DB.
        Get the list of prefixes for the existing Data in the storage.
        Get the list of commands and their sequence numbers.
        Get the latest comand execution sequence.
        """
        prefixes_msg = PrefixesInStorage()
        ret = self.storage.get('prefixes')
        if ret:
            prefixes_msg.ParseFromString(ret)
            for prefix in prefixes_msg.prefixes:
                logging.info('Existing prefix found: {:s}'.format(prefix.name))
                self.read_handle.listen(Name(prefix.name))
        
        commands_msg = CommandsInStorage()
        ret = self.storage.get('commands')
        if ret:
            commands_msg.ParseFromString(ret)
            for command in commands_msg.commands:
                cmd = Interest()
                cmd.wireDecode(Blob(command.interest))
                self.cmd_handle.seq_to_cmd[command.seq] = cmd
                logging.info('Existing command found: {}'.format(command.seq))
        
        ret = self.storage.get('exec_seq')
        if ret:
            exec_seq = int.from_bytes(ret, byteorder='little')
            self.cmd_handle.exec_seq = exec_seq
            logging.info('Existing exec seq found: {}'.format(exec_seq))

    @staticmethod
    def on_register_failed(prefix):
        logging.error("Prefix registration failed: %s", prefix)
