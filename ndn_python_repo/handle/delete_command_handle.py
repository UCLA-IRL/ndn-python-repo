import asyncio as aio
import logging
import random
import sys
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName, Component, DecodeError
from . import ReadHandle, CommandHandle
from ..command.repo_commands import RepoCommandParameter, RepoCommandResponse
from ..storage import Storage
from ..utils import PubSub


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

    async def listen(self, prefix: NonStrictName):
        """
        Register routes for command interests.
        This function needs to be called explicitly after initialization.

        :param name: NonStrictName. The name prefix to listen on.
        """
        self.prefix = prefix

        # subscribe to delete messages
        self.pb.subscribe(self.prefix + ['delete'], self._on_delete_msg)

        # listen on delete check interests
        self.app.route(self.prefix + ['delete check'])(self._on_check_interest)

    def _on_delete_msg(self, msg):
        try:
            cmd_param = RepoCommandParameter.parse(msg)
            if cmd_param.name == None:
                raise DecodeError()
        except (DecodeError, IndexError) as exc:
            logging.warning('Parameter interest decoding failed')
            return
        aio.ensure_future(self._process_delete(cmd_param))

    async def _process_delete(self, cmd_param: RepoCommandParameter):
        """
        Process delete command.
        Return to client with status code 100 immediately, and then start data fetching process.
        """
        try:
            name = cmd_param.name
            start_block_id = cmd_param.start_block_id if cmd_param.start_block_id else 0
            end_block_id = cmd_param.end_block_id if cmd_param.end_block_id else sys.maxsize
            process_id = cmd_param.process_id
            if cmd_param.register_prefix:
                register_prefix = cmd_param.register_prefix.name
            else:
                register_prefix = None
            check_prefix = cmd_param.check_prefix.name
        except AttributeError:
            return

        logging.info(f'Delete handle processing delete command: {Name.to_str(name)}, {start_block_id}, {end_block_id}')

        # Reply to client with status code 100
        self.m_processes[process_id] = RepoCommandResponse()
        self.m_processes[process_id].process_id = process_id
        self.m_processes[process_id].delete_num = 0

        # If repo does not register root prefix, the client tells repo what to unregister
        if register_prefix:
            is_existing = CommandHandle.remove_registered_prefix_in_storage(self.storage, register_prefix)
            if not self.register_root and is_existing:
                self.m_read_handle.unlisten(register_prefix)

        # Remember what files are removed
        CommandHandle.remove_inserted_filename_in_storage(self.storage, name)

        # Perform delete
        self.m_processes[process_id].status_code = 300
        delete_num = await self._perform_storage_delete(name, start_block_id, end_block_id)
        logging.info('Deletion success, {} items deleted'.format(delete_num))

        # Delete complete, update process state
        self.m_processes[process_id].status_code = 200
        self.m_processes[process_id].delete_num = delete_num

        # Remove process state after some time
        await self._delete_process_state_after(process_id, 60)

    async def _perform_storage_delete(self, prefix, start_block_id: int, end_block_id: int) -> int:
        """
        Delete data packets between [start_block_id, end_block_id]. If end_block_id is None, delete
        all continuous data packets from start_block_id.
        :param prefix: NonStrictName.
        :param start_block_id: int.
        :param end_block_id: int.
        :return: The number of data items deleted.
        """
        delete_num = 0
        for idx in range(start_block_id, end_block_id + 1):
            key = prefix + [Component.from_segment(idx)]
            if self.storage.get_data_packet(key) != None:
                self.storage.remove_data_packet(key)
                delete_num += 1
            else:
                # assume sequence numbers are continuous
                break
            # Temporarily release control to make the process non-blocking
            await aio.sleep(0)
        return delete_num
