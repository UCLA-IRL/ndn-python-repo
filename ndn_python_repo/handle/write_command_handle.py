import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.security.validator import sha256_digest_checker
from ndn.encoding import Name, NonStrictName
from . import ReadHandle, CommandHandle
from .ingest_handle import DirectIngestHandle
from ..command import RepoCommandRes, RepoCommandParam, ObjParam, ObjStatus, RepoStatCode
from ..utils import PubSub
from ..storage import Storage
from typing import Optional
from .utils import normalize_block_ids, fetch_object


class WriteCommandHandle(CommandHandle):
    """
    WriteCommandHandle processes insert command interests, and fetches corresponding data to
    store them into the database.
    TODO: Add validator
    """
    def __init__(self, app: NDNApp, storage: Storage, pb: PubSub, ingest_handle: Optional[DirectIngestHandle], read_handle: ReadHandle,
                 config: dict):
        """
        Write handle need to keep a reference to write handle to register new prefixes.

        :param app: NDNApp.
        :param storage: Storage.
        :param read_handle: ReadHandle. This param is necessary, because WriteCommandHandle need to
            call ReadHandle.listen() to register new prefixes.
        :param ingest_handle: DirectIngestHandle or None. If provided, registers the direct ingest
            protocol alongside the legacy pub-sub insert protocol.
        """
        super(WriteCommandHandle, self).__init__(app, storage, pb, config)
        self.m_read_handle = read_handle
        self.m_ingest_handle = ingest_handle
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

        # subscribe to insert messages
        self.pb.subscribe(self.prefix + Name.from_str('insert'), self._on_insert_msg)

        # listen on insert check interests
        self.app.attach_handler(self.prefix + Name.from_str('insert check'), self._on_check_interest,
                                sha256_digest_checker)
        
        # direct ingest protocol
        if self.m_ingest_handle is not None:
            await self.m_ingest_handle.listen(prefix)
            
    def _on_insert_msg(self, msg):
        cmd_param, request_no = self.parse_msg(msg)
        aio.create_task(self._process_insert(cmd_param, request_no))

    async def _process_insert(self, cmd_param: RepoCommandParam, request_no: bytes):
        """
        Process segmented insertion command.
        Return to client with status code 100 immediately, and then start data fetching process.
        """
        objs = cmd_param.objs
        self.logger.info(f'Recved insert command: {request_no.hex()}')

        # Cached status response
        # Note: no coroutine switching here, so no multithread conflicts
        def _init_obj_stat(obj: ObjParam) -> ObjStatus:
            ret = ObjStatus()
            ret.name = obj.name
            ret.status_code = RepoStatCode.ROGER
            ret.insert_num = 0
            ret.delete_num = None
            return ret

        # Note: stat is hold by reference
        stat = RepoCommandRes()
        stat.status_code = RepoStatCode.IN_PROGRESS
        stat.objs = [_init_obj_stat(obj) for obj in objs]
        self.m_processes[request_no] = stat

        # Start fetching
        global_inserted = 0
        global_succeeded = True
        for i, obj in enumerate(objs):
            name = obj.name
            if obj.register_prefix and obj.register_prefix.name:
                register_prefix = obj.register_prefix.name
            else:
                register_prefix = None

            self.logger.debug(f'Proc ins cmd {request_no.hex()} w/'
                          f'name={Name.to_str(name)}, start={obj.start_block_id}, end={obj.end_block_id}')

            # rejects any data that overlaps with repo's own namespace
            if Name.is_prefix(self.prefix, name) or Name.is_prefix(name, self.prefix):
                self.logger.warning('Inserted data name overlaps with repo prefix, rejected')
                stat.objs[i].status_code = RepoStatCode.MALFORMED
                global_succeeded = False
                continue
            valid, _, _ = normalize_block_ids(obj)
            if not valid:
                self.logger.warning('Insert command malformed')
                stat.objs[i].status_code = RepoStatCode.MALFORMED
                global_succeeded = False
                continue

            # Remember the prefixes to register
            if register_prefix:
                is_existing = CommandHandle.add_registered_prefix_in_storage(self.storage, register_prefix)
                # If repo does not register root prefix, the client tells repo what to register
                if not self.register_root and not is_existing:
                    self.m_read_handle.listen(register_prefix)

            # Remember the files inserted, this is useful for enumerating all inserted files
            # CommandHandle.add_inserted_filename_in_storage(self.storage, name)

            # Start data fetching process
            stat.objs[i].status_code = RepoStatCode.IN_PROGRESS
            status_code, insert_num = await fetch_object(self.app, self.storage, obj)
            stat.objs[i].status_code = status_code

            if status_code == RepoStatCode.COMPLETED:
                self.logger.info(f'Insertion {request_no.hex()} name={Name.to_str(name)} finish:'
                             f'{insert_num} inserted')
            else:
                global_succeeded = False
                self.logger.info(f'Insertion {request_no.hex()} name={Name.to_str(name)} fail:'
                             f'{insert_num} inserted')
            stat.objs[i].insert_num = insert_num
            global_inserted += insert_num

        # All fetches finished
        self.logger.info(f'Insertion {request_no.hex()} done, total {global_inserted} inserted.')
        if global_succeeded:
            stat.status_code = RepoStatCode.COMPLETED
        else:
            stat.status_code = RepoStatCode.FAILED

        # Delete process state after some time
        await self._delete_process_state_after(request_no, 60)
