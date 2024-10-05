import asyncio as aio
import io
import logging
import sys
from . import ReadHandle, CommandHandle
from ..storage import *
from ndn.encoding import Name, read_tl_num_from_stream, parse_data
from ndn.encoding import TypeNumber, FormalName


class TcpBulkInsertHandle(object):

    class TcpBulkInsertClient(object):
        """
        An instance of this nested class will be created for every new connection.
        """
        def __init__(self, reader, writer, storage: Storage, read_handle: ReadHandle, config: dict):
            """
            TCP Bulk insertion client need to keep a reference to ReadHandle to register new prefixes.
            """
            self.logger = logging.getLogger(__name__)
            self.reader = reader
            self.writer = writer
            self.storage = storage
            self.read_handle = read_handle
            self.config = config
            self.m_inputBufferSize = 0
            prefix_strs = self.config['tcp_bulk_insert'].get('prefixes', [])
            self.reg_root = self.config['repo_config']['register_root']
            self.reg_prefix = self.config['tcp_bulk_insert']['register_prefix']
            self.prefixes = [Name.from_str(s) for s in prefix_strs]
            self.logger.info("New connection")

        async def handle_receive(self):
            """
            Handle one incoming TCP connection.
            Multiple data packets may be transferred over a single connection.
            """
            while True:
                try:
                    bio = io.BytesIO()
                    ret = await read_tl_num_from_stream(self.reader, bio)
                    # only accept data packets
                    if ret != TypeNumber.DATA:
                        self.logger.fatal('TCP handle received non-data type, closing connection ...')
                        self.writer.close()
                        return
                    siz = await read_tl_num_from_stream(self.reader, bio)
                    bio.write(await self.reader.readexactly(siz))
                    data_bytes = bio.getvalue()
                except aio.IncompleteReadError:
                    self.writer.close()
                    self.logger.info('Closed TCP connection')
                    return
                except Exception as exc:
                    print(exc)
                    return
                # Parse data again to obtain the name
                data_name, _, _, _ = parse_data(data_bytes, with_tl=True)
                self.storage.put_data_packet(data_name, data_bytes)
                self.logger.info(f'Inserted data: {Name.to_str(data_name)}')

                # Register prefix
                if not self.reg_root and self.reg_prefix:
                    prefix = self.check_prefix(data_name)
                    self.logger.info(f'Try to register prefix: {Name.to_str(prefix)}')
                    is_existing = CommandHandle.add_registered_prefix_in_storage(self.storage, prefix)
                    if not is_existing:
                        self.logger.info(f'Registered prefix: {Name.to_str(prefix)}')
                        self.read_handle.listen(prefix)

                await aio.sleep(0)

        def check_prefix(self, data_name: FormalName) -> FormalName:
            for prefix in self.prefixes:
                if Name.is_prefix(prefix, data_name):
                    return prefix
            return data_name

    def __init__(self, storage: Storage, read_handle: ReadHandle, config: dict):
        """
        TCP bulk insertion handle need to keep a reference to ReadHandle to register new prefixes.
        """
        self.logger = logging.getLogger(__name__)

        async def run():
            self.server = await aio.start_server(self.start_receive, server_addr, server_port)
            addr = self.server.sockets[0].getsockname()
            self.logger.info(f'TCP insertion handle serving on {addr}')
            async with self.server:
                await self.server.serve_forever()

        self.storage = storage
        self.read_handle = read_handle
        self.config = config

        server_addr = self.config['tcp_bulk_insert']['addr']
        server_port = self.config['tcp_bulk_insert']['port']
        event_loop = aio.get_event_loop()

        if sys.version_info.minor >= 7:
            # python 3.7+
            event_loop.create_task(run())
        else:
            coro = aio.start_server(self.start_receive, server_addr, server_port, loop=event_loop)
            server = event_loop.run_until_complete(coro)
            self.logger.info('TCP insertion handle serving on {}'.format(server.sockets[0].getsockname()))

    async def start_receive(self, reader, writer):
        """
        Create a new client for every new connection.
        """
        self.logger.info("Accepted new TCP connection")
        client = TcpBulkInsertHandle.TcpBulkInsertClient(reader, writer, self.storage, self.read_handle, self.config)
        event_loop = aio.get_event_loop()
        event_loop.create_task(client.handle_receive())


if __name__ == "__main__":
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    storage = LevelDBStorage() # fixme: this should have a parameter for the location of the db
    handle = TcpBulkInsertHandle(storage) # fixme: read_handle and config parameters are unfilled

    event_loop = aio.get_event_loop()
    event_loop.run_forever()
