import os
import sys
import asyncio
import logging
from pyndn import Face, Name, Data, Interest
from pyndn.security import KeyChain

from storage import Storage
from handle import WriteHandle, ReadHandle, DeleteHandle


class Repo(object):
    def __init__(self, prefix: Name, face: Face, storage: Storage, write_handle: WriteHandle,
                 read_handle: ReadHandle, delete_handle: DeleteHandle):
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
        self.read_handle.listen(self.prefix)
        self.delete_handle.listen(self.prefix)

    @staticmethod
    def on_register_failed(prefix):
        logging.error("Prefix registration failed: %s", prefix)

