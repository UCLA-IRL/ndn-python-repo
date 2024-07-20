import logging
from ndn.app import NDNApp
from ndn.encoding import Name

from .storage import *
from .handle import *


class Repo(object):
    def __init__(self, app: NDNApp, storage: Storage, read_handle: ReadHandle,
                 write_handle: WriteCommandHandle, delete_handle: DeleteCommandHandle,
                 sync_handle: SyncCommandHandle, tcp_bulk_insert_handle: TcpBulkInsertHandle, config: dict):
        """
        An NDN repo instance.
        """
        self.prefix = Name.from_str(config['repo_config']['repo_name'])
        self.app = app
        self.storage = storage
        self.write_handle = write_handle
        self.read_handle = read_handle
        self.delete_handle = delete_handle
        self.sync_handle = sync_handle
        self.tcp_bulk_insert_handle = tcp_bulk_insert_handle

        self.running = True
        self.register_root = config['repo_config']['register_root']
        self.logger = logging.getLogger(__name__)

    async def listen(self):
        """
        Configure pubsub to listen on prefix. The handles share the same pb, so only need to be
        done once.

        This method need to be called to make repo working.
        """
        # Recover registered prefix to enable hot restart
        if not self.register_root:
            self.recover_registered_prefixes()
        self.recover_sync_states()

        # Init PubSub
        self.write_handle.pb.set_publisher_prefix(self.prefix)
        self.write_handle.pb.set_base_prefix(self.prefix)
        self.delete_handle.pb.set_base_prefix(self.prefix)
        self.sync_handle.pb.set_base_prefix(self.prefix)
        await self.write_handle.pb.wait_for_ready()

        await self.write_handle.listen(self.prefix)
        await self.delete_handle.listen(self.prefix)
        await self.sync_handle.listen(self.prefix)

    def recover_registered_prefixes(self):
        prefixes = self.write_handle.get_registered_prefix_in_storage(self.storage)
        for prefix in prefixes:
            self.logger.info(f'Existing Prefix Found: {Name.to_str(prefix)}')
            self.read_handle.listen(prefix)

    def recover_sync_states(self):
        states = {}
        groups = self.sync_handle.get_sync_groups_in_storage(self.storage)
        for group in groups:
            group_states = self.sync_handle.get_sync_states_in_storage(self.storage, group)
            states[Name.to_str(group)] = group_states
        self.sync_handle.recover_from_states(states)