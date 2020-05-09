import abc
import asyncio as aio
from ndn.app import NDNApp
from ndn.encoding import Name, ndn_format_0_3
from ndn.transport.dummy_face import DummyFace
from ndn.security import KeychainDigest
from ndn_python_repo.utils.concurrent_fetcher import concurrent_fetcher
import pytest


class ConcurrentFetcherTestSuite(object):
    """
    Abstract test fixture to simulate packet send and recv.
    """
    def test_main(self):
        face = DummyFace(self.face_proc)
        keychain = KeychainDigest()
        self.app = NDNApp(face, keychain)
        face.app = self.app
        self.app.run_forever(after_start=self.app_main())
    
    @abc.abstractmethod
    async def face_proc(self, face: DummyFace):
        pass

    @abc.abstractmethod
    async def app_main(self):
        pass


class TestConcurrentFetcherBasic(ConcurrentFetcherTestSuite):
    async def face_proc(self, face: DummyFace):
        await face.consume_output(b'\x05"\x07\x1c\x08\x17test_concurrent_fetcher!\x01\x00\x0c\x02\x03\xe8',
                                  timeout=1)
        await face.input_packet(b"\x06\x9d\x07\x1c\x08\x17test_concurrent_fetcher!\x01\x00\x14\x07\x18\x01\x00\x19\x02'\x10\x15\rHello, world!\x16\x1c\x1b\x01\x03\x1c\x17\x07\x15\x08\x04test\x08\x03KEY\x08\x08\xa0\x04\xf7\xe7\xdd\x0f\x17\xbd\x17G0E\x02!\x00\x8bD\x12\xacOuY[\xab[\xe3\x04\xea\xd7J\x07\xecxa\x14\x8d\x88\xf0\xa4\xe5\xf0\x96\xaeI\xfd\xe5\x90\x02 W,/\x13\xf7\xec\x90\xa5*\xdea\x94\xe9\xa6e5\x15\xbd\xc8P\xa5\xbf\xbeu*um\xf2[XI\xc8")

    async def app_main(self):
        semaphore = aio.Semaphore(1)
        async for (data_name, _, _, _) in concurrent_fetcher(self.app, Name.from_str('/test_concurrent_fetcher'), 0, 0, semaphore, nonce=None):
            assert Name.to_str(data_name) == '/test_concurrent_fetcher/seg=0'