import abc
import asyncio as aio
from ndn.app import NDNApp
from ndn.encoding import Name, ndn_format_0_3
from ndn.transport.dummy_face import DummyFace
from ndn.security import KeychainDigest
from ndn_python_repo.concurrent_fetcher import concurrent_fetcher
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
        await face.consume_output(b'\x05\x11\x07\t\x08\x04test\x08\x010\x12\x00\x0c\x02\x03\xe8')
        await face.input_packet(b'\x06?\x07\t\x08\x04test\x08\x010\x14\x03\x18\x01\x00\x15\x06foobar'
                                b'\x16\x03\x1b\x01\x00\x17 \x94?\\\xae\x99\xd5\xd6\xa5\x18\xac\x00'
                                b'\xe3\xcaX\x82\x972,\xf1\xebUQ\xa5I%\xb3\xd5\xac\xcc\xc6\x80Q')

    async def app_main(self):
        semaphore = aio.Semaphore(1)
        async for (data_name, _, _, _) in concurrent_fetcher(self.app, Name.from_str('/test'), 0, 0, semaphore, nonce=None):
            assert Name.to_str(data_name) == '/test/0'