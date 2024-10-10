import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName, Component
from typing import Optional
from . import ReadHandle, CommandHandle
from ..command import RepoCommandRes, RepoCommandParam, ObjParam, ObjStatus, RepoStatCode
from ..storage import Storage
from ..utils import PubSub
from .utils import normalize_block_ids


class DeleteCommandHandle(CommandHandle):
    """
    DeleteCommandHandle processes delete command handles, and deletes corresponding data stored
    in the database.
    TODO: Add validator
    """
    def __init__(self, app: NDNApp, storage: Storage, pb: PubSub, read_handle: ReadHandle,
                 config: dict):
        """
        Read handle need to keep a reference to write handle to register new prefixes.

        :param app: NDNApp.
        :param storage: Storage.
        :param read_handle: ReadHandle. This param is necessary because DeleteCommandHandle need to
            unregister prefixes.
        """
        super(DeleteCommandHandle, self).__init__(app, storage, pb, config)
        self.m_read_handle = read_handle
        self.prefix = None
        self.register_root = config['repo_config']['register_root']
        self.logger = logging.getLogger(__name__)

    async def listen(self, prefix: NonStrictName):
        """
        Register routes for command interests.
        This function needs to be called explicitly after initialization.

        :param prefix: NonStrictName. The name prefix to listen on.
        """
        self.prefix = Name.normalize(prefix)

        # subscribe to delete messages
        self.pb.subscribe(self.prefix + Name.from_str('delete'), self._on_delete_msg)

        # listen on delete check interests
        self.app.set_interest_filter(self.prefix + Name.from_str('delete check'), self._on_check_interest)

    def _on_delete_msg(self, msg):
        cmd_param, request_no = self.parse_msg(msg)
        aio.create_task(self._process_delete(cmd_param, request_no))

    async def _process_delete(self, cmd_param: RepoCommandParam, request_no: bytes):
        """
        Process delete command.
        """
        objs = cmd_param.objs
        self.logger.info(f'Received delete command: {request_no.hex()}')

        # Note that this function still has chance to switch coroutine in _perform_storage_delete.
        # So status is required to be defined before actual deletion
        def _init_obj_stat(obj: ObjParam) -> ObjStatus:
            ret = ObjStatus()
            ret.name = obj.name
            ret.status_code = RepoStatCode.ROGER
            ret.insert_num = None
            ret.delete_num = 0
            return ret

        # Note: stat is hold by reference
        stat = RepoCommandRes()
        stat.status_code = RepoStatCode.IN_PROGRESS
        stat.objs = [_init_obj_stat(obj) for obj in objs]
        self.m_processes[request_no] = stat

        global_deleted = 0
        global_succeeded = True
        for i, obj in enumerate(objs):
            name = obj.name
            valid, start_id, end_id = normalize_block_ids(obj)
            if not valid:
                self.logger.warning('Delete command malformed')
                stat.objs[i].status_code = RepoStatCode.MALFORMED
                global_succeeded = False
                continue

            self.logger.debug(f'Proc del cmd {request_no.hex()} w/'
                          f'name={Name.to_str(name)}, start={obj.start_block_id}, end={obj.end_block_id}')

            # Start data deleting process
            stat.objs[i].status_code = RepoStatCode.IN_PROGRESS

            # If repo does not register root prefix, the client tells repo what to unregister
            # TODO: It is probably improper to let the client remember which prefix is registered.
            # When register_prefix differs from the insertion command, unexpected result may arise.
            if obj.register_prefix:
                register_prefix = obj.register_prefix.name
            else:
                register_prefix = None
            if register_prefix:
                is_existing = CommandHandle.remove_registered_prefix_in_storage(self.storage, register_prefix)
                if not self.register_root and is_existing:
                    self.m_read_handle.unlisten(register_prefix)

            # Remember what files are removed
            # TODO: Warning: this code comes from previous impl.
            # When start_id and end_id differs from the insertion command, unexpected result may arise.
            # Please do not let such case happen until we fix this problem.
            # CommandHandle.remove_inserted_filename_in_storage(self.storage, name)

            # Perform delete
            if start_id is not None:
                delete_num = await self._perform_storage_delete(name, start_id, end_id)
            else:
                delete_num = await self._delete_single_data(name)
            self.logger.info(f'Deletion {request_no.hex()} name={Name.to_str(name)} finish:'
                         f'{delete_num} deleted')

            # Delete complete, update process state
            stat.objs[i].status_code = RepoStatCode.COMPLETED
            stat.objs[i].delete_num = delete_num
            global_deleted += delete_num

        # All fetches finished
        self.logger.info(f'Deletion {request_no.hex()} done, total {global_deleted} deleted.')
        if global_succeeded:
            stat.status_code = RepoStatCode.COMPLETED
        else:
            stat.status_code = RepoStatCode.FAILED

        # Remove process state after some time
        await self._delete_process_state_after(request_no, 60)

    async def _perform_storage_delete(self, prefix, start_block_id: int, end_block_id: Optional[int]) -> int:
        """
        Delete data packets between [start_block_id, end_block_id]. If end_block_id is None, delete
        all continuous data packets from start_block_id.
        :param prefix: NonStrictName.
        :param start_block_id: int.
        :param end_block_id: int.
        :return: The number of data items deleted.
        """
        delete_num = 0
        if end_block_id is None:
            end_block_id = 2 ** 30  # TODO: For temp use; Should discover
        for idx in range(start_block_id, end_block_id + 1):
            key = prefix + [Component.from_segment(idx)]
            if self.storage.get_data_packet(key) is not None:
                self.logger.debug(f'Data for key {Name.to_str(key)} to be deleted.')
                self.storage.remove_data_packet(key)
                delete_num += 1
            else:
                # assume sequence numbers are continuous
                self.logger.debug(f'Data for key {Name.to_str(key)} not found, break.')
                break
            # Temporarily release control to make the process non-blocking
            await aio.sleep(0)
        return delete_num

    # TODO: previous version only uses _perform_storage_delete
    # I doubt if it properly worked. So need test for the current change.
    # NOTE: this test cannot done by a client because
    #  1) the prefix has been unregistered, so undeleted data become ghost.
    #  2) the current client always uses segmented insertion/deletion
    async def _delete_single_data(self, name) -> int:
        """
        Delete data packets between [start_block_id, end_block_id]. If end_block_id is None, delete
        all continuous data packets from start_block_id.
        :param name: The name of data to be deleted.
        :return: The number of data items deleted.
        """
        if self.storage.get_data_packet(name) is not None:
            self.storage.remove_data_packet(name)
            await aio.sleep(0)
            return 1
        else:
            return 0
