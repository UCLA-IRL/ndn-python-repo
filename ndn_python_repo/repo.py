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
    
    async def listen(self):
        await self.write_handle.listen(self.prefix)
        await self.delete_handle.listen(self.prefix)

    @staticmethod
    def on_register_failed(prefix):
        logging.error(f'Prefix registration failed: {prefix}')
