import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName
from ndn.types import InterestNack, InterestTimeout
from . import ReadHandle, CommandHandle
from ..command import RepoCommandRes, RepoCommandParam, ObjParam, ObjStatus, RepoStatCode
from ..utils import concurrent_fetcher, PubSub
from ..storage import Storage
from typing import Optional
from .utils import normalize_block_ids


class WriteCommandHandle(CommandHandle):
    """
    WriteCommandHandle processes insert command interests, and fetches corresponding data to
    store them into the database.
    TODO: Add validator
    """
    def __init__(self, app: NDNApp, storage: Storage, pb: PubSub, read_handle: ReadHandle,
                 config: dict):
        """
        Write handle need to keep a reference to write handle to register new prefixes.

        :param app: NDNApp.
        :param storage: Storage.
        :param read_handle: ReadHandle. This param is necessary, because WriteCommandHandle need to
            call ReadHandle.listen() to register new prefixes.
        """
        super(WriteCommandHandle, self).__init__(app, storage, pb, config)
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

        # subscribe to insert messages
        self.pb.subscribe(self.prefix + Name.from_str('insert'), self._on_insert_msg)

        # listen on insert check interests
        self.app.set_interest_filter(self.prefix + Name.from_str('insert check'), self._on_check_interest)

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
            if obj.forwarding_hint and obj.forwarding_hint.names:
                forwarding_hint = obj.forwarding_hint.names
            else:
                forwarding_hint = None

            self.logger.debug(f'Proc ins cmd {request_no.hex()} w/'
                          f'name={Name.to_str(name)}, start={obj.start_block_id}, end={obj.end_block_id}')

            # rejects any data that overlaps with repo's own namespace
            if Name.is_prefix(self.prefix, name) or Name.is_prefix(name, self.prefix):
                self.logger.warning('Inserted data name overlaps with repo prefix, rejected')
                stat.objs[i].status_code = RepoStatCode.MALFORMED
                global_succeeded = False
                continue
            valid, start_block_id, end_block_id = normalize_block_ids(obj)
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

            if start_block_id is not None:
                # Fetch data packets with block ids appended to the end
                insert_num = await self.fetch_segmented_data(name, start_block_id, end_block_id, forwarding_hint)
                is_success = end_block_id is None or start_block_id + insert_num - 1 == end_block_id
            else:
                # Both start_block_id and end_block_id are None, fetch a single data packet
                insert_num = await self.fetch_single_data(name, forwarding_hint)
                is_success = insert_num == 1

            if is_success:
                stat.objs[i].status_code = RepoStatCode.COMPLETED
                self.logger.info(f'Insertion {request_no.hex()} name={Name.to_str(name)} finish:'
                             f'{insert_num} inserted')
            else:
                global_succeeded = False
                stat.objs[i].status_code = RepoStatCode.FAILED
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

    async def fetch_single_data(self, name: NonStrictName, forwarding_hint: Optional[list[NonStrictName]]):
        """
        Fetch one Data packet.
        :param name: NonStrictName.
        :param forwarding_hint: Optional[list[NonStrictName]]
        :return:  Number of data packets fetched.
        """
        try:
            data_name, _, _, data_bytes = await self.app.express_interest(
                name, need_raw_packet=True, can_be_prefix=False, lifetime=1000,
                forwarding_hint=forwarding_hint)
        except InterestNack as e:
            self.logger.info(f'Nacked with reason={e.reason}')
            return 0
        except InterestTimeout:
            self.logger.info(f'Timeout')
            return 0
        self.storage.put_data_packet(data_name, data_bytes)
        return 1

    async def fetch_segmented_data(self, name, start_block_id: int, end_block_id: Optional[int],
                                   forwarding_hint: Optional[list[NonStrictName]]):
        """
        Fetch segmented Data packets.
        :param name: NonStrictName.
        :param start_block_id: int
        :param end_block_id: Optional[int]
        :param forwarding_hint: Optional[list[NonStrictName]]
        :return: Number of data packets fetched.
        """
        semaphore = aio.Semaphore(10)
        block_id = start_block_id
        async for (data_name, _, _, data_bytes) in (
                concurrent_fetcher(self.app, name, start_block_id, end_block_id,
                                   semaphore, forwarding_hint=forwarding_hint)):
            self.storage.put_data_packet(data_name, data_bytes)
            block_id += 1
        insert_num = block_id - start_block_id
        return insert_num
