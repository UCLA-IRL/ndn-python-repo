import asyncio as aio
import logging
from hashlib import sha256

from ndn.app import NDNApp
from ndn.encoding import Component, DecodeError, Name, NonStrictName, parse_data

from ..command import (
    RepoCommandParam,
    RepoCommandRes,
    RepoStatCode,
    SyncParam,
    SyncStatus,
)
from ..storage import Storage
from ..utils import concurrent_fetcher, IdNamingConv, PassiveSvs, PubSub
from . import CommandHandle, ReadHandle


class SyncCommandHandle(CommandHandle):
    """
    SyncCommandHandle processes insert command interests, and fetches corresponding data to
    store them into the database.
    TODO: Add validator
    """

    def __init__(
        self,
        app: NDNApp,
        storage: Storage,
        pb: PubSub,
        read_handle: ReadHandle,
        config: dict,
    ):
        """
        Sync handle need to keep a reference to sync handle to register new prefixes.

        :param app: NDNApp.
        :param storage: Storage.
        :param read_handle: ReadHandle. This param is necessary, because WriteCommandHandle need to
            call ReadHandle.listen() to register new prefixes.
        """
        super(SyncCommandHandle, self).__init__(app, storage, pb, config)
        self.m_read_handle = read_handle
        self.prefix = None
        self.register_root = config["repo_config"]["register_root"]
        # sync specific states
        self.states_on_disk = {}
        # runtime states
        self.running_svs = {}
        self.running_fetcher = {}

    async def listen(self, prefix: NonStrictName):
        """
        Register routes for command interests.
        This function needs to be called explicitly after initialization.

        :param prefix: NonStrictName. The name prefix to listen on.
        """
        self.prefix = Name.normalize(prefix)

        # subscribe to sync messages
        self.pb.subscribe(self.prefix + Name.from_str("sync/join"), self._on_sync_msg)

        # subscribe to leave messages
        self.pb.subscribe(self.prefix + Name.from_str("sync/leave"), self._on_leave_msg)

    def recover_from_states(self, states: dict):
        self.states_on_disk = states
        # recover sync
        for sync_group, group_states in self.states_on_disk.items():
            new_svs = PassiveSvs(sync_group, lambda svs: self.fetch_missing_data(svs))
            new_svs.decode_from_states(group_states["svs_client_states"])
            logging.info(f"Recover sync for {Name.to_str(sync_group)}")
            group_fetched_dict = group_states["fetched_dict"]
            logging.info(f"Sync progress: {group_fetched_dict}")
            new_svs.start(self.app)
            self.running_svs[Name.to_str(sync_group)] = new_svs

    def _on_sync_msg(self, msg):
        try:
            cmd_param = RepoCommandParam.parse(msg)
            request_no = sha256(bytes(msg)).digest()
            if not cmd_param.sync_groups:
                raise DecodeError("Missing sync groups")
            for group in cmd_param.sync_groups:
                if not group.sync_prefix or not group.sync_prefix.name:
                    raise DecodeError("Missing name for one or more sync groups")
                if group.register_prefix and group.register_prefix.name:
                    if group.sync_prefix.name == group.register_prefix.name:
                        raise DecodeError(
                            "Sync prefix and register prefix cannot be the same"
                        )
        except (DecodeError, IndexError) as exc:
            logging.warning(
                f"Parameter interest blob decoding failed w/ exception: {exc}"
            )
            return
        aio.create_task(self._process_sync(cmd_param, request_no))

    def _on_leave_msg(self, msg):
        try:
            cmd_param = RepoCommandParam.parse(msg)
            request_no = sha256(bytes(msg)).digest()
            if not cmd_param.sync_groups:
                raise DecodeError("Missing sync groups")
            for group in cmd_param.sync_groups:
                if not group.sync_prefix or not group.sync_prefix.name:
                    raise DecodeError("Missing name for one or more sync groups")
        except (DecodeError, IndexError) as exc:
            logging.warning(
                f"Parameter interest blob decoding failed w/ exception: {exc}"
            )
            return
        aio.create_task(self._process_leave(cmd_param, request_no))

    async def _process_sync(self, cmd_param: RepoCommandParam, request_no: bytes):
        """
        Process sync command.
        Return to client with status code 100 immediately, and then start sync process.
        """
        groups = cmd_param.sync_groups
        logging.info(f"Received sync command: {request_no.hex()}")

        # Cached status response
        # Note: no coroutine switching here, so no multithread conflicts
        def _init_sync_stat(param: SyncParam) -> SyncStatus:
            ret = SyncStatus()
            ret.name = param.sync_prefix.name
            ret.status_code = RepoStatCode.ROGER
            return ret

        # Note: stat is hold by reference
        stat = RepoCommandRes()
        stat.status_code = RepoStatCode.IN_PROGRESS
        stat.sync_groups = [_init_sync_stat(group) for group in groups]
        self.m_processes[request_no] = stat
        # start sync
        for idx, group in enumerate(groups):
            # check duplicate
            sync_prefix = Name.to_str(group.sync_prefix.name)
            if sync_prefix in self.states_on_disk:
                # if asking for reset
                if group.reset:
                    if sync_prefix in self.running_fetcher:
                        for task in self.running_fetcher.pop(sync_prefix):
                            task.cancel()
                    if sync_prefix in self.running_svs:
                        svs = self.running_svs[sync_prefix]
                        # rebuild state vectors from actual storage
                        group_states = self.states_on_disk[sync_prefix]
                        svs.local_sv = group_states["fetched_dict"]
                        logging.info(f"Rebuild state vectors to: {svs.local_sv}")
                        svs.inst_buffer = {}
                        group_states["svs_client_states"] = svs.encode_into_states()
                        CommandHandle.add_sync_states_in_storage(
                            self.storage,
                            group.sync_prefix.name,
                            self.states_on_disk[sync_prefix],
                        )
                    logging.info(f"Reset sync for: {sync_prefix}")
                    continue
                else:
                    logging.info(f"Duplicate sync for: {sync_prefix}")
                    continue
            new_svs = PassiveSvs(
                group.sync_prefix.name, lambda psvs: self.fetch_missing_data(psvs)
            )
            new_svs.start(self.app)
            self.running_svs[sync_prefix] = new_svs
            # write states
            self.states_on_disk[sync_prefix] = {}
            new_states = self.states_on_disk[sync_prefix]
            new_states["fetched_dict"] = {}
            new_states["svs_client_states"] = {}
            new_states["data_name_dedupe"] = group.data_name_dedupe
            new_states["check_status"] = {}
            # Remember the prefixes to register
            if group.register_prefix and group.register_prefix.name:
                new_states["register_prefix"] = Name.to_str(group.register_prefix.name)
                is_existing = CommandHandle.add_registered_prefix_in_storage(
                    self.storage, group.register_prefix.name
                )
                # If repo does not register root prefix, the client tells repo what to register
                if not self.register_root and not is_existing:
                    self.m_read_handle.listen(group.register_prefix.name)
            else:
                new_states["register_prefix"] = None
            CommandHandle.add_sync_group_in_storage(self.storage, group.sync_prefix.name)
            new_states["svs_client_states"] = new_svs.encode_into_states()
            CommandHandle.add_sync_states_in_storage(
                self.storage, group.sync_prefix.name, new_states
            )

    async def _process_leave(self, cmd_param: RepoCommandParam, request_no: bytes):
        groups = cmd_param.sync_groups
        logging.info(f"Received leave command: {request_no.hex()}")

        for idx, group in enumerate(groups):
            sync_prefix = Name.to_str(group.sync_prefix.name)
            if sync_prefix in self.states_on_disk:
                states = self.states_on_disk[sync_prefix]
                logging.info(f"Leaving sync for: {sync_prefix}")
                if sync_prefix in self.running_fetcher:
                    for task in self.running_fetcher.pop(sync_prefix):
                        task.cancel()

                if sync_prefix in self.running_svs:
                    svs = self.running_svs.pop(sync_prefix)
                    await svs.stop()

                # Unregister prefix
                if states["register_prefix"]:
                    register_prefix = Name.from_str(states["register_prefix"])
                    CommandHandle.remove_registered_prefix_in_storage(
                        self.storage, Name.from_str(states["register_prefix"])
                    )
                    if not self.register_root:
                        self.m_read_handle.unlisten(register_prefix)

                CommandHandle.remove_sync_states_in_storage(
                    self.storage, group.sync_prefix.name
                )
                CommandHandle.remove_sync_group_in_storage(
                    self.storage, group.sync_prefix.name
                )

                self.states_on_disk.pop(sync_prefix)
            else:
                logging.info(f"Leaving sync group that does not exist: {sync_prefix}")

    def fetch_missing_data(self, svs: PassiveSvs):
        if not svs.running:
            return

        local_sv = svs.local_sv.copy()
        for node_id, seq in local_sv.items():
            task = aio.create_task(self.node_fetcher(svs, node_id, seq))
            self.running_fetcher[Name.to_str(svs.base_prefix)] = task

    # this deals with specific producer. this function is blocking, until receiving all
    # data (segments) from the producer
    async def node_fetcher(self, svs, node_id, seq):
        group_states = self.states_on_disk[Name.to_str(svs.base_prefix)]
        group_fetched_dict = group_states["fetched_dict"]
        group_data_name_dedupe = group_states["data_name_dedupe"]
        fetched_seq = group_fetched_dict.get(node_id, 0)
        node_name = Name.from_str(node_id) + svs.base_prefix
        if group_data_name_dedupe:
            data_prefix = [i for n, i in enumerate(node_name) if i not in node_name[:n]]
        else:
            data_prefix = node_name
        # I do not treat fetching failure as hard failure
        if fetched_seq < seq:
            async for data_name, _, data_content, data_bytes in concurrent_fetcher(
                self.app,
                data_prefix,
                start_id=fetched_seq + 1,
                end_id=seq,
                semaphore=aio.Semaphore(10),
                name_conv=IdNamingConv.SEQUENCE,
            ):
                # put into storage asap
                self.storage.put_data_packet(data_name, data_bytes)
                # not very sure the side effect
                group_fetched_dict[node_id] = Component.to_number(data_name[-1])
                logging.info(f"Sync progress: {group_fetched_dict}")
                group_states["svs_client_states"] = svs.encode_into_states()
                CommandHandle.add_sync_states_in_storage(
                    self.storage, svs.base_prefix, group_states
                )
                """
                Python-repo specific logic: if the inner data content contains a data name,
                assuming the data object pointed by is segmented, and fetching all
                data segments related to this object name
                """
                try:
                    _, _, inner_data_content, _ = parse_data(data_content)
                    obj_pointer = Name.from_bytes(inner_data_content)
                except (TypeError, IndexError, ValueError):
                    logging.debug(f"Data does not include an object pointer, skip")
                    continue
                logging.info(
                    f"Discovered a pointer, fetching data segments for {Name.to_str(obj_pointer)}"
                )
                async for loop_data_name, _, _, loop_data_bytes in concurrent_fetcher(
                    self.app,
                    obj_pointer,
                    start_id=0,
                    end_id=None,
                    semaphore=aio.Semaphore(10),
                ):
                    self.storage.put_data_packet(loop_data_name, loop_data_bytes)
