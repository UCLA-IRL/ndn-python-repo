import logging
from ndn.app import NDNApp
from ndn.encoding import Name

from .storage import *
from .handle import *
from .command.repo_commands import PrefixesInStorage


class Repo(object):
    def __init__(self, prefix, app: NDNApp, storage: Storage, read_handle: ReadHandle,
                 write_handle: WriteCommandHandle, delete_handle: DeleteCommandHandle,
                 tcp_bulk_insert_handle: TcpBulkInsertHandle):
        """
        Registers routable prefix, and calls listen() on all handles.
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
        ret = self.storage._get(b'prefixes')
        if ret:
            prefixes_msg = PrefixesInStorage.parse(ret)
            for prefix in prefixes_msg.prefixes:
                logging.info(f'Existing Prefix Found: {Name.to_str(prefix)}')
                self.read_handle.listen(prefix)

    @staticmethod
    def on_register_failed(prefix):
        logging.error(f'Prefix registration failed: {prefix}')
