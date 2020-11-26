import asyncio as aio
import io
import logging
import pickle
import sys
from . import ReadHandle, CommandHandle
from ..storage import *
from ndn.encoding import Name, read_tl_num_from_stream, parse_data
from ndn.encoding import TypeNumber


class TcpBulkInsertHandle(object):

    class TcpBulkInsertClient(object):
        """
        An instance of this nested class will be created for every new connection.
        """
        def __init__(self, reader, writer, storage: Storage, read_handle: ReadHandle, config: dict):
            """
            TCP Bulk insertion client need to keep a reference to ReadHandle to register new prefixes.
            """
            self.reader = reader
            self.writer = writer
            self.storage = storage
            self.read_handle = read_handle
            self.config = config
            self.m_inputBufferSize = 0
            logging.info("New connection")

        async def handleReceive(self):
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
                        logging.fatal('TCP handle received non-data type, closing connection ...')
                        self.writer.close()
                        return
                    siz = await read_tl_num_from_stream(self.reader, bio)
                    bio.write(await self.reader.readexactly(siz))
                    data_bytes = bio.getvalue()
                except aio.IncompleteReadError as exc:
                    self.writer.close()
                    logging.info('Closed TCP connection')
                    return
                except Exception as exc:
                    print(exc)
                    return
                # Parse data again to obtain the name
                data_name, _, _, _ = parse_data(data_bytes, with_tl=True)
                self.storage.put_data_packet(data_name, data_bytes)
                logging.info(f'Inserted data: {Name.to_str(data_name)}')

                # Register prefix
                if not self.config['repo_config']['register_root'] and self.config['tcp_bulk_insert']['register_prefix']:
                    is_existing = CommandHandle.add_registered_prefix_in_storage(self.storage, data_name)
                    if not is_existing:
                        self.read_handle.listen(data_name)

                await aio.sleep(0)

    def __init__(self, storage: Storage, read_handle: ReadHandle, config: dict):
        """
        TCP bulk insertion handle need to keep a reference to ReadHandle to register new prefixes.
        """
        async def run():
            self.server = await aio.start_server(self.startReceive, server_addr, server_port)
            addr = self.server.sockets[0].getsockname()
            logging.info(f'TCP insertion handle serving on {addr}')
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
            coro = aio.start_server(self.startReceive, server_addr, server_port, loop=event_loop)
            server = event_loop.run_until_complete(coro)
            logging.info('TCP insertion handle serving on {}'.format(server.sockets[0].getsockname()))

    async def startReceive(self, reader, writer):
        """
        Create a new client for every new connection.
        """
        logging.info("Accepted new TCP connection")
        client = TcpBulkInsertHandle.TcpBulkInsertClient(reader, writer, self.storage, self.read_handle, self.config)
        event_loop = aio.get_event_loop()
        event_loop.create_task(client.handleReceive())


if __name__ == "__main__":
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    storage = LevelDBStorage()
    handle = TcpBulkInsertHandle(storage)

    event_loop = aio.get_event_loop()
    event_loop.run_forever()
