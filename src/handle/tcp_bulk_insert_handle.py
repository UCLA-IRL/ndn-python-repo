import asyncio
import logging
import pickle
import sys
# from pyndn import Data
from . import ReadHandle, CommandHandle
from src.storage import *
# from pyndn.encoding.tlv_0_2_wire_format import Tlv0_2WireFormat

BUFFER_SIZE = 8000


class TcpBulkInsertHandle(object):

    class TcpBulkInsertClient(object):
        """
        An instance of this nested class will be created for every new connection.
        """
        def __init__(self, reader, writer, storage: Storage, read_handle: ReadHandle):
            """
            TCP Bulk insertion client need to keep a reference to ReadHandle to register new prefixes.
            """
            self.reader = reader
            self.writer = writer
            self.storage = storage
            self.read_handle = read_handle
            self.buffer = bytearray(BUFFER_SIZE)
            self.m_inputBufferSize = 0
            logging.info("New connection")

        async def handleReceive(self):
            """
            Handle one incoming TCP connection.
            Multiple data packets may be transferred over a single connection.
            """
            logging.info("handleReceive()")

            data_bytes = await self.reader.read(len(self.buffer) - self.m_inputBufferSize)
            self.buffer = self.buffer[:self.m_inputBufferSize] + data_bytes + bytearray(len(self.buffer) - self.m_inputBufferSize - len(data_bytes))
            assert len(self.buffer) == BUFFER_SIZE
            nBytesReceived = len(data_bytes)

            # Read 0 bytes means the other side has closed the connection
            if nBytesReceived == 0:
                logging.info('Otherside closed connection')
                return
            self.m_inputBufferSize += nBytesReceived

            isOk = True
            offset = 0
            while self.m_inputBufferSize - offset > 0:
                data = Data()
                decoder = Tlv0_2WireFormat()

                try:
                    decoder.decodeData(data, self.buffer[offset:], False)
                except ValueError:
                    logging.warning('Decoding failed')
                    isOk = False
                    break

                # Obtain data size by encoding it again
                offset += len(decoder.encodeData(data)[0])
                assert offset <= self.m_inputBufferSize
                self.storage.put(str(data.getName()), pickle.dumps(data.wireEncode().toBytes()))

                logging.info('Inserted data: {}'.format(str(data.getName())))
                existing = CommandHandle.update_prefixes_in_storage(self.storage, data.getName().toUri())
                if not existing:
                    self.read_handle.listen(data.getName())


            # If buffer is filled up with un-parsable data, shutdown connection
            if not isOk and self.m_inputBufferSize == len(self.buffer) and offset == 0:
                logging.warning('Invalid data packet, drop connection ...')
                self.writer.close()
                return

            if offset > 0:
                if offset != self.m_inputBufferSize:
                    self.buffer = self.buffer[offset : self.m_inputBufferSize] + bytearray(len(self.buffer) - self.m_inputBufferSize + offset)
                    assert len(self.buffer) == BUFFER_SIZE
                    self.m_inputBufferSize -= offset
                else:
                    self.m_inputBufferSize = 0

            event_loop = asyncio.get_event_loop()
            event_loop.create_task(self.handleReceive())

    def __init__(self, storage: Storage, read_handle: ReadHandle,
                 server_addr: str, server_port: str):     # TODO: address and port
        """
        TCP bulk insertion handle need to keep a reference to ReadHandle to register new prefixes.
        """
        async def run():
            self.server = await asyncio.start_server(self.startReceive, server_addr, server_port)
            addr = self.server.sockets[0].getsockname()
            logging.info(f'Serving on {addr}')
            async with self.server:
                await self.server.serve_forever()

        self.storage = storage
        self.read_handle = read_handle
        event_loop = asyncio.get_event_loop()
        
        if sys.version_info.minor >= 7:
            # python 3.7+
            event_loop.create_task(run())
        else:
            coro = asyncio.start_server(self.startReceive, server_addr, server_port, loop=event_loop)
            server = event_loop.run_until_complete(coro)
            logging.info('Serving on {}'.format(server.sockets[0].getsockname()))

    async def startReceive(self, reader, writer):
        """
        Create a new client for every new connection.
        """
        logging.info("Waiting for connection ... ")
        client = TcpBulkInsertHandle.TcpBulkInsertClient(reader, writer, self.storage, self.read_handle)
        event_loop = asyncio.get_event_loop()
        event_loop.create_task(client.handleReceive())


if __name__ == "__main__":
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    storage = LevelDBStorage()
    handle = TcpBulkInsertHandle(storage)

    event_loop = asyncio.get_event_loop()
    event_loop.run_forever()
