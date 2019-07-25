import os
import sys
import asyncio
import logging
from pyndn import Face, Name, Data, Interest
from pyndn.security import KeyChain

from storage import Storage
from handle import ReadHandle, WriteCommandHandle, DeleteCommandHandle
from command.repo_storage_format_pb2 import PrefixesInStorage


class Repo(object):
    def __init__(self, prefix: Name, face: Face, storage: Storage, read_handle: ReadHandle,
                 write_handle: WriteCommandHandle, delete_handle: DeleteCommandHandle):
        """
        Registers routable prefix, and calls listen() on all handles
        TODO: Remove face as input, put it in handles only
        TODO: Remove storage as input, put it in handles only
        """
        self.prefix = prefix
        self.face = face
        self.storage = storage
        self.write_handle = write_handle
        self.read_handle = read_handle
        self.delete_handle = delete_handle
        self.running = True

        self.face.registerPrefix(self.prefix, None, self.on_register_failed)
        self.write_handle.listen(self.prefix)
        self.delete_handle.listen(self.prefix)

    def recover_previous_prefixes(self):
        """
        Read from the database and get the a list of prefixes for the existing Data in the storage
        """
        prefixes_msg = PrefixesInStorage()
        ret = self.storage.get("prefixes")
        if ret:
            prefixes_msg.ParseFromString(ret)
            for prefix in prefixes_msg.prefixes:
                logging.info("Existing Prefix Found: {:s}".format(prefix.name))
                self.read_handle.listen(Name(prefix.name))
        pass

    @staticmethod
    def on_register_failed(prefix):
        logging.error("Prefix registration failed: %s", prefix)
