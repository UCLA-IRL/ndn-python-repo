import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName, DecodeError, FormalName, InterestParam, BinaryStr
from ndn.types import InterestNack, InterestTimeout
from . import ReadHandle, CommandHandle
from ..command.repo_commands import RepoCommandParameter, RepoCommandResponse, CatalogCommandParameter,\
 CatalogResponseParameter, CatalogDataListParameter, CatalogInsertParameter, CatalogDeleteParameter,\
 CatalogDataFetchParameter
from ..utils import concurrent_fetcher, PubSub
from ..storage import Storage
from typing import Optional
from ndn.utils import gen_nonce


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
        self.catalog = config['catalog']

    async def listen(self, prefix: NonStrictName):
        """
        Register routes for command interests.
        This function needs to be called explicitly after initialization.

        :param perfix: NonStrictName. The name prefix to listen on.
        """
        self.prefix = prefix

        # subscribe to insert messages
        self.pb.subscribe(self.prefix + ['insert'], self._on_insert_msg)

        # listen on insert check interests
        self.app.route(self.prefix + ['insert check'])(self._on_check_interest)

        aio.ensure_future(self.fetch_listen())

    def _on_insert_msg(self, msg):
        try:
            cmd_param = RepoCommandParameter.parse(msg)
            if cmd_param.name == None:
                raise DecodeError()
        except (DecodeError, IndexError) as exc:
            logging.warning('Parameter interest blob decoding failed')
            return
        aio.ensure_future(self._process_insert(cmd_param))

    async def _process_insert(self, cmd_param: RepoCommandParameter):
        """
        Process segmented insertion command.
        Return to client with status code 100 immediately, and then start data fetching process.
        """
        name = cmd_param.name
        start_block_id = cmd_param.start_block_id
        end_block_id = cmd_param.end_block_id
        process_id = cmd_param.process_id
        register_prefix = cmd_param.register_prefix

        logging.info(f'Write handle processing insert command: {Name.to_str(name)}, {start_block_id}, {end_block_id}')

        # rejects any data that overlaps with repo's own namespace
        if Name.is_prefix(self.prefix, name) or Name.is_prefix(name, self.prefix):
            logging.warning('Inserted data name overlaps with repo prefix')
            return
        elif self.is_valid_param(cmd_param) == False:
            logging.warning('Insert command malformed: only end_block_id is specified')
            return

        # Reply to client with status code 100
        self.m_processes[process_id] = RepoCommandResponse()
        self.m_processes[process_id].process_id = process_id
        self.m_processes[process_id].insert_num = 0

        # If repo does not register root prefix, the client tells repo what to register
        if not self.register_root:
            if not CommandHandle.add_prefixes_in_storage(self.storage, register_prefix):
                self.m_read_handle.listen(register_prefix)

        # Start data fetching process
        self.m_processes[process_id].status_code = 300
        insert_num = 0
        is_success = False
        if start_block_id != None:
            # Fetch data packets with block ids appended to the end
            insert_num = await self.fetch_segmented_data(name, start_block_id, end_block_id)
            if end_block_id is None or start_block_id + insert_num - 1 == end_block_id:
                is_success = True
        else:
            # Both start_block_id and end_block_id are None, fetch a single data packet
            insert_num = await self.fetch_single_data(name)
            if insert_num == 1:
                is_success = True

        if is_success:
            self.m_processes[process_id].status_code = 200
            logging.info('Insertion success, {} items inserted'.format(insert_num))
        else:
            self.m_processes[process_id].status_code = 400
            logging.info('Insertion failure, {} items inserted'.format(insert_num))
        self.m_processes[process_id].insert_num = insert_num

        await self.check_insert(name)

        # Delete process state after some time
        await self.schedule_delete_process(process_id)

    def is_valid_param(self, cmd_param):
        """
        Validate insert parameter.
        :param cmd_param: RepoCommandParameter.
        :return: Is valid param.
        """
        start_block_id = cmd_param.start_block_id
        end_block_id = cmd_param.end_block_id
        # can't have start_block_id not specified, but end_block_id specified
        if start_block_id == None and end_block_id != None:
            return False
        elif start_block_id != None and end_block_id != None:
            if start_block_id > end_block_id:
                return False

    async def fetch_single_data(self, name):
        """
        Fetch one Data packet.
        :param name: NonStrictName.
        :return:  Number of data packets fetched.
        """
        try:
            data_name, _, _, data_bytes = await self.app.express_interest(
                name, need_raw_packet=True, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
        except InterestNack as e:
            logging.info(f'Nacked with reason={e.reason}')
            return 0
        except InterestTimeout:
            logging.info(f'Timeout')
            return 0
        self.storage.put_data_packet(data_name, data_bytes)
        return 1

    async def fetch_segmented_data(self, name, start_block_id: int, end_block_id: Optional[int]):
        """
        Fetch segmented Data packets.
        :param name: NonStrictName.
        :return: Number of data packets fetched.
        """
        semaphore = aio.Semaphore(10)
        block_id = start_block_id
        async for (data_name, _, _, data_bytes) in concurrent_fetcher(self.app, name, start_block_id, end_block_id, semaphore):
            self.storage.put_data_packet(data_name, data_bytes)
            block_id += 1
        insert_num = block_id - start_block_id
        return insert_num

    async def fetch_listen(self):
        """
        Starts listening for /prefix/fetch_map interests and sends insertion data to
        the catalog when requests is received.
        """
        name = self.prefix + ["fetch_map"]
        logging.debug("Listening: {}".format(Name.to_str(name)))
        self.app.route(name)(self._on_interest)

    async def check_insert(self, data_name):
        """
        Sends an interest to the catalog and waits for acknowledgement which is basically an
        empty data packet. Once it gets an acknowledgement it knows that the catalog received the
        request. The module then does nothing and waits for data request from the catalog. Once
        the request is received the client responds with a list of insertions and deletions.
        :param catalog_name: the name of the catalog to which to send the insertion request.
        """
        method = 'insert'
        cmd_param = CatalogCommandParameter()
        cmd_param.name = self.prefix
        cmd_param.data_name = data_name
        cmd_param_bytes = cmd_param.encode()

        name = Name.from_str(self.catalog)
        name += [method]
        self.nonce = gen_nonce()
        name += [str(self.nonce)]
        logging.info("Name: {}".format(Name.to_str(name)))
        try:
            aio.ensure_future(self.send_interest(name, cmd_param_bytes))
        except InterestNack:
            logging.debug(">>>NACK")
            return
        except InterestTimeout:
            logging.debug(">>>TIMEOUT")
            return

    async def send_interest(self, name: FormalName, cmd_param_bytes: bytes):
        """
        Sends interest to the catalog.
        :param name: name to send the interest to
        :param cmd_param_bytes: app parameters containing client prefix.
        """
        _, _, data_bytes = await self.app.express_interest(
            name, app_param=cmd_param_bytes, must_be_fresh=True, can_be_prefix=False)
        logging.info("> ACK RECVD: {}".format(bytes(data_bytes)))

    def _on_interest(self, int_name: FormalName, int_param: InterestParam, app_param: Optional[BinaryStr]):
        """
        Callback for data request from Catalog.
        :param int_name: the interest name received.
        :param int_param: the interest params received.
        :param app_param: the app params received.
        """
        logging.info("FETCH REQUEST {}".format(Name.to_str(int_name)))
        aio.ensure_future(self._process_interest(int_name, int_param, app_param))

    async def _process_interest(self, int_name: FormalName, int_param: InterestParam, app_param: Optional[BinaryStr]):
        """
        Makes a new CatalogDataListParameter object containing all the insertion params and deletion params.
        Every insert parameter contains the data name, the name to map the data to and the expiry time for
        insertions. Also, checks the status of insertion request.
        :param int_name: the interest name received.
        :param int_param: the interest params received.
        :param app_param: the app params received.
        """
        cmd_param = CatalogDataListParameter()

        recvd_param = CatalogDataFetchParameter.parse(app_param)
        param = CatalogInsertParameter()
        param.data_name = recvd_param.data_name
        param.name = self.prefix
        param.expire_time_ms = 3600

        cmd_param.insert_data_names = [param]
        cmd_param.delete_data_names = []
        cmd_param = cmd_param.encode()

        self.app.put_data(int_name, bytes(cmd_param), freshness_period=500)

        # CHECK STATUS
        # await aio.sleep(5)
        # logging.info("Status Check Request Sent...")
        # name = Name.from_str(self.catalog_name)
        # name += ['check']
        # name += [str(self.nonce)]
        # name += [str(gen_nonce())]
        # _, _, data_bytes = await self.app.express_interest(
        #     name, must_be_fresh=True, can_be_prefix=False)
        # response = CatalogResponseParameter.parse(data_bytes)
        # logging.info("Status Received: {}".format(response.status))
        # self.app.shutdown()