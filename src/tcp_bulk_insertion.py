import asyncio
import logging
import pickle

from pyndn import Blob, Face, Name, Data, Interest, NetworkNack
from pyndn.security import KeyChain
from pyndn import encoding
from pyndn.encoding.tlv_0_2_wire_format import Tlv0_2WireFormat
from storage import Storage, LevelDBStorage

SERVER_ADDRESS = '0.0.0.0'
SEVER_PORT = '7376'
NDN_PACKET_MAX_SIZE = 8000

class TcpBulkInsertHandle(object):

    class TcpBulkInsertClient(object):
        def __init__(self, reader, writer, storage: Storage):
            self.reader = reader
            self.writer = writer
            self.storage = storage
            self.buffer = bytearray(NDN_PACKET_MAX_SIZE)
            self.m_inputBufferSize = 0
            logging.info("New connection")
        
        async def handleReceive(self):
            logging.info("handleReceive()")
            
            data_bytes = await self.reader.read(len(self.buffer) - self.m_inputBufferSize)
            self.buffer = self.buffer[:self.m_inputBufferSize] + data_bytes + bytearray(len(self.buffer) - self.m_inputBufferSize - len(data_bytes))
            assert len(self.buffer) == NDN_PACKET_MAX_SIZE

            print(data_bytes)
            nBytesReceived = len(data_bytes)
            if nBytesReceived == 0:
                # TODO: double check
                logging.info('Otherside closed connection')
                return

            self.m_inputBufferSize += nBytesReceived

            isOk = True
            offset = 0
            while self.m_inputBufferSize - offset > 0:
                data = Data()
                decoder = Tlv0_2WireFormat()
                try:
                    print('Going to decode {} bytes: '.format(nBytesReceived))
                    print(data_bytes)
                    decoder.decodeData(data, self.buffer[offset:], False)
                except ValueError:
                    logging.warning('Decoding failed')  # TODO: Remove
                    # TODO: non-Data packets will cause infinite loop
                    isOk = False
                    break

                # Obtain data size by encoding it again
                offset += len(decoder.encodeData(data)[0])
                assert offset <= self.m_inputBufferSize

                self.storage.put(str(data.getName()), pickle.dumps(data.wireEncode().toBytes()))
                logging.info('Inserted data: {}'.format(str(data.getName())))
            
            # If buffer is filled up with un-parsable data, shutdown connection
            if not isOk and self.m_inputBufferSize == len(self.buffer) and offset == 0:
                logging.warining('Invalid data packet, drop connection ...')
                self.writer.close()
                return
            
            if offset > 0:
                if offset != self.m_inputBufferSize:
                    self.buffer = self.buffer[offset : self.m_inputBufferSize] + bytearray(len(self.buffer) - self.m_inputBufferSize + offset)
                    assert len(self.buffer) == NDN_PACKET_MAX_SIZE
                    self.m_inputBufferSize -= offset
                else:
                    self.m_inputBufferSize = 0

            # await self.handleReceive()
            event_loop = asyncio.get_event_loop()
            event_loop.create_task(self.handleReceive())
    

    def __init__(self, storage: Storage):     # TODO: address and port
        async def run():
            self.server = await asyncio.start_server(self.startReceive, SERVER_ADDRESS, SEVER_PORT)
            addr = self.server.sockets[0].getsockname()
            logging.info(f'Serving on {addr}')
            async with self.server:
                await self.server.serve_forever()

        self.storage = storage
        asyncio.run(run())

    
    async def startReceive(self, reader, writer):
        logging.info("Waiting for connection ... ")
        client = TcpBulkInsertHandle.TcpBulkInsertClient(reader, writer, self.storage)
        event_loop = asyncio.get_event_loop()
        event_loop.create_task(client.handleReceive())


if __name__ == "__main__":
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    # TODO: Remove hard-coded things
    storage = LevelDBStorage()
    handle = TcpBulkInsertHandle(storage)