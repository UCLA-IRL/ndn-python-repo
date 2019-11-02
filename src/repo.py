import logging
from ndn.app import NDNApp
from ndn.encoding import Name

from src.storage import *
from src.handle import *
from src.command.repo_storage_format_pb2 import PrefixesInStorage


class Repo(object):
    def __init__(self, prefix, app: NDNApp, storage: Storage, read_handle: ReadHandle,
                 write_handle: WriteCommandHandle, delete_handle: DeleteCommandHandle,
                 tcp_bulk_insert_handle: TcpBulkInsertHandle):
        """
        Registers routable prefix, and calls listen() on all handles
        TODO: Remove face as input, put it in handles only
        TODO: Remove storage as input, put it in handles only
        """
        self.prefix = prefix
        self.app = app
        self.storage = storage
        self.write_handle = write_handle
        self.read_handle = read_handle
        self.delete_handle = delete_handle
        self.tcp_bulk_insert_handle = tcp_bulk_insert_handle
        self.running = True
    
    def listen(self):
        self.recover_previous_prefixes()
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
                self.read_handle.listen(Name.from_str(prefix.name))
        pass

    @staticmethod
    def on_register_failed(prefix):
        logging.error("Prefix registration failed: %s", prefix)
