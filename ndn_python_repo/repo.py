import logging
from ndn.app import NDNApp
from ndn.encoding import Name

from .storage import *
from .handle import *
from .command.repo_commands import PrefixesInStorage


class Repo(object):
    def __init__(self, app: NDNApp, storage: Storage, read_handle: ReadHandle,
                 write_handle: WriteCommandHandle, delete_handle: DeleteCommandHandle,
                 tcp_bulk_insert_handle: TcpBulkInsertHandle, config: dict):
        """
        An NDN repo instance.
        """
        self.prefix = Name.from_str(config['repo_config']['repo_name'])
        self.app = app
        self.storage = storage
        self.write_handle = write_handle
        self.read_handle = read_handle
        self.delete_handle = delete_handle
        self.tcp_bulk_insert_handle = tcp_bulk_insert_handle
        self.running = True

    async def listen(self):
        """
        Configure pubsub to listen on prefix. The handles share the same pb, so only need to be
        done once.

        This method need to be called to make repo working.
        """
        self.write_handle.pb.set_prefix(self.prefix)
        await self.write_handle.pb.wait_for_ready()

        await self.write_handle.listen(self.prefix)
        await self.delete_handle.listen(self.prefix)