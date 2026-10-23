import asyncio as aio
import base64
import filecmp
import multiprocessing
from datetime import datetime, timezone
from Cryptodome.PublicKey import ECC
from ndn.app import NDNApp
from ndn.app_support.security_v2 import self_sign, derive_cert
from ndn.encoding import Name, Component, ContentType
from ndn.security import KeychainDigest, DigestSha256Signer, Sha256WithEcdsaSigner
from ndn.types import InterestNack, InterestTimeout
from ndn_python_repo.clients import GetfileClient, PutfileClient, DeleteClient, CommandChecker, IngestClient
from ndn_python_repo.clients.ingest import _CommandSigner
from ndn_python_repo.command import RepoCommandParam, ObjParam, RepoStatCode, EmbName
from ndn_python_repo.utils import PubSub
import os
import platform
import subprocess
import tempfile
import uuid
from hashlib import sha256


sqlite3_path = os.path.join(tempfile.mkdtemp(), 'sqlite3_test.db')
repo_name = 'testrepo'
register_root = False
port = 7377


def create_ingest_pki():
    """Create a trust anchor, a producer certificate it signs, and an LVS schema for ingest."""
    tmp_dir = tempfile.mkdtemp()
    root_key = ECC.generate(curve='P-256')
    root_key_name = Name.from_str('/test-root/KEY/root')
    root_cert_name, root_cert = self_sign(
        root_key_name, root_key.public_key().export_key(format='DER'),
        Sha256WithEcdsaSigner(root_key_name, root_key.export_key(format='DER')))
    producer_key = ECC.generate(curve='P-256')
    producer_cert_name, producer_cert = derive_cert(
        Name.from_str('/ingest_client/KEY/producer'), 'root',
        producer_key.public_key().export_key(format='DER'),
        Sha256WithEcdsaSigner(root_cert_name, root_key.export_key(format='DER')),
        datetime.now(timezone.utc), 3600)

    anchor_path = os.path.join(tmp_dir, 'anchor.ndncert')
    with open(anchor_path, 'wb') as f:
        f.write(base64.b64encode(bytes(root_cert)))
    schema_path = os.path.join(tmp_dir, 'ingest.lvs')
    with open(schema_path, 'w') as f:
        f.write(f'''
#KEY: "KEY"/_/_/_
#root: "test-root"/#KEY
#producer: "ingest_client"/#KEY <= #root
#ingest: "{repo_name}"/"ingest"/_ <= #producer
''')
    signer = Sha256WithEcdsaSigner(producer_cert_name, producer_key.export_key(format='DER'))
    return anchor_path, schema_path, producer_cert_name, bytes(producer_cert), signer


(ingest_anchor_path, ingest_schema_path,
 producer_cert_name, producer_cert, producer_signer) = create_ingest_pki()

inline_cfg = f"""
---
repo_config:
  repo_name: {repo_name}
  register_root: {register_root}
db_config:
  db_type: sqlite3
  sqlite3:
    path: {sqlite3_path}
  leveldb: 
    dir: ~/.ndn/ndn-python-repo/leveldb/
  mongodb:
    db: test_python_repo
    collection: ndn_data
    uri: mongodb://127.0.0.1:27017/
ingest_security:
  trust_anchor: {ingest_anchor_path}
  trust_schema: {ingest_schema_path}
tcp_bulk_insert:
  addr: 0.0.0.0
  port: {port}
  register_prefix: True
  prefixes:
  - /test
logging_config:
  level: INFO 
"""


class RepoTestSuite(object):

    def test_main(self):
        # could not get NFD running on travis macos, skipping ...
        if os.getenv('TRAVIS') and platform.system() == 'Darwin':
            return
        self.startup()
        self.cleanup()

    def startup(self):
        self.files_to_cleanup = []

        tmp_cfg_path = self.create_tmp_cfg()
        self.files_to_cleanup.append(tmp_cfg_path)
        self.files_to_cleanup.append(sqlite3_path)
        self.repo_proc = subprocess.Popen(['ndn-python-repo', '-c', tmp_cfg_path])

        self.app = NDNApp(face=None, keychain=KeychainDigest())
        self.app.run_forever(after_start=self.run())

    def cleanup(self):
        self.repo_proc.kill()
        for file in self.files_to_cleanup:
            if os.path.exists(file):
                print('Cleaning up tmp file:', file)
                os.remove(file)

    @staticmethod
    def create_tmp_file(size_bytes=4096):
        tmp_file_path = os.path.join(tempfile.mkdtemp(), 'tempfile')
        with open(tmp_file_path, 'wb') as f:
            f.write(os.urandom(size_bytes))
        return tmp_file_path

    @staticmethod
    def create_tmp_cfg():
        tmp_cfg_path = os.path.join(tempfile.mkdtemp(), 'ndn-python-repo.cfg')
        with open(tmp_cfg_path, 'w') as f:
            f.write(inline_cfg)
        return tmp_cfg_path

    async def run(self):
        pass

    async def serve_producer_cert(self):
        """Serve the producer certificate so the repo can fetch the ingest signing chain."""
        await self.app.register(producer_cert_name,
                                lambda int_name, _p, _a: self.app.put_raw_packet(producer_cert))


class TestBasic(RepoTestSuite):
    async def run(self):
        await aio.sleep(2)  # wait for repo to startup
        filepath1 = self.create_tmp_file(size_bytes=10 * 1024)
        filepath2 = uuid.uuid4().hex.upper()[0:6]

        # put
        pc = PutfileClient(self.app, Name.from_str('/putfile_client'), Name.from_str(repo_name))
        insert_num = await pc.insert_file(filepath1, Name.from_str(filepath2), segment_size=8000,
            freshness_period=0, cpu_count=multiprocessing.cpu_count())
        # get
        gc = GetfileClient(self.app, Name.from_str(repo_name))
        await gc.fetch_file(Name.from_str(filepath2))
        # diff
        assert filecmp.cmp(filepath1, filepath2)
        # delete
        dc = DeleteClient(self.app, Name.from_str('/delete_client'), Name.from_str(repo_name))
        delete_num = await dc.delete_file(Name.from_str(filepath2))
        print("Insert: {}, delete: {}".format(insert_num, delete_num))
        assert insert_num == delete_num
        # cleanup
        self.files_to_cleanup.append(filepath1)
        self.files_to_cleanup.append(filepath2)
        self.app.shutdown()


class TestIngest(RepoTestSuite):
    async def run(self):
        await aio.sleep(2)  # wait for repo to startup
        data_name = uuid.uuid4().hex.upper()[0:6]
        content = b'foobar'

        await self.serve_producer_cert()

        # ingest a single Data packet
        ic = IngestClient(self.app, Name.from_str('/ingest_client'), Name.from_str(repo_name))
        success = await ic.ingest_data(Name.from_str(data_name), content,
                                       register_prefix=Name.from_str(data_name),
                                       signer=producer_signer)
        assert success

        # fetch it back from the repo and check content
        _, _, fetched_content = await self.app.express_interest(Name.from_str(data_name))
        assert bytes(fetched_content) == content

        self.app.shutdown()


class TestIngestSegmented(RepoTestSuite):
    async def run(self):
        await aio.sleep(2)  # wait for repo to startup
        data_name = Name.from_str(uuid.uuid4().hex.upper()[0:6])
        segments = [b'segment-zero', b'segment-one', b'segment-two']
        final_block_id = Component.from_segment(len(segments) - 1)

        encoded_segments = {}
        for seq, content in enumerate(segments):
            seg_name = data_name + [Component.from_segment(seq)]
            encoded_segments[Name.to_str(seg_name)] = self.app.prepare_data(
                seg_name, content, final_block_id=final_block_id)

        def on_interest(int_name, _int_param, _app_param):
            name_str = Name.to_str(int_name)
            if name_str in encoded_segments:
                self.app.put_raw_packet(encoded_segments[name_str])

        await self.app.register(data_name, on_interest)
        await self.serve_producer_cert()

        # ingest a segmented object, letting end_block_id auto-detect from final_block_id
        cmd_param = ObjParam()
        cmd_param.name = data_name
        cmd_param.start_block_id = 0
        cmd_param.register_prefix = EmbName.from_name(data_name)

        int_name = Name.from_str(repo_name) + Name.from_str('ingest')
        _, meta_info, _ = await self.app.express_interest(
            int_name, cmd_param.encode(), can_be_prefix=False, lifetime=10000,
            signer=_CommandSigner(producer_signer))
        assert meta_info.content_type != ContentType.NACK

        # fetch each segment back from the repo and check content
        for seq, content in enumerate(segments):
            _, _, fetched_content = await self.app.express_interest(data_name + [Component.from_segment(seq)])
            assert bytes(fetched_content) == content

        self.app.shutdown()


class TestIngestNack(RepoTestSuite):
    async def run(self):
        await aio.sleep(2)  # wait for repo to startup
        int_name = Name.from_str(repo_name) + Name.from_str('ingest')
        await self.serve_producer_cert()

        # unsigned parameterized Interests are explicitly rejected
        cmd_param = ObjParam()
        cmd_param.name = Name.from_str(uuid.uuid4().hex.upper()[0:6])
        _, meta_info, _ = await self.app.express_interest(
            int_name, cmd_param.encode(), can_be_prefix=False, lifetime=1000, no_signature=True)
        assert meta_info.content_type == ContentType.NACK

        # Interests not signed by a key the trust schema authorizes are dropped, not answered
        cmd_param = ObjParam()
        cmd_param.name = Name.from_str(uuid.uuid4().hex.upper()[0:6])
        try:
            await self.app.express_interest(
                int_name, cmd_param.encode(), can_be_prefix=False, lifetime=1000,
                signer=DigestSha256Signer(for_interest=True))
            assert False, 'repo replied to an unauthorized ingest command'
        except InterestTimeout:
            pass

        # single Data packet that nobody serves: repo must NACK, not stay silent
        cmd_param = ObjParam()
        cmd_param.name = Name.from_str(uuid.uuid4().hex.upper()[0:6])
        nack_name, meta_info, _ = await self.app.express_interest(
            int_name, cmd_param.encode(), can_be_prefix=False, lifetime=10000,
            signer=_CommandSigner(producer_signer))
        assert meta_info.content_type == ContentType.NACK

        # resending the same command is a new signed Interest with a new name
        retry_name, meta_info, _ = await self.app.express_interest(
            int_name, cmd_param.encode(), can_be_prefix=False, lifetime=10000,
            signer=_CommandSigner(producer_signer))
        assert meta_info.content_type == ContentType.NACK
        assert retry_name != nack_name

        # segmented object with auto-detected end where no segment can be fetched:
        # zero segments stored must not be acknowledged as success
        cmd_param = ObjParam()
        cmd_param.name = Name.from_str(uuid.uuid4().hex.upper()[0:6])
        cmd_param.start_block_id = 0
        _, meta_info, _ = await self.app.express_interest(
            int_name, cmd_param.encode(), can_be_prefix=False, lifetime=10000,
            signer=_CommandSigner(producer_signer))
        assert meta_info.content_type == ContentType.NACK

        self.app.shutdown()


class TestBundle(RepoTestSuite):
    async def run(self):
        await aio.sleep(2)  # wait for repo to startup

        # respond to interest from repo
        def on_int_1(int_name, _int_param, _app_param):
            self.app.put_data(int_name, b'foo', freshness_period=1000)

        def on_int_2(int_name, _int_param, _app_param):
            self.app.put_data(int_name, b'bar', freshness_period=1000)

        await self.app.register('test_foo', on_int_1)
        await self.app.register('test_bar', on_int_2)

        # construct insert parameter
        cmd_param = RepoCommandParam()
        cmd_param.objs = [ObjParam(), ObjParam()]
        cmd_param.objs[0].name = 'test_foo'
        cmd_param.objs[0].forwarding_hint = None
        cmd_param.objs[0].start_block_id = 0
        cmd_param.objs[0].end_block_id = 0
        cmd_param.objs[0].register_prefix = None
        cmd_param.objs[1].name = 'test_bar'
        cmd_param.objs[1].forwarding_hint = None
        cmd_param.objs[1].start_block_id = None
        cmd_param.objs[1].end_block_id = None
        cmd_param.objs[1].register_prefix = None

        cmd_param_bytes = bytes(cmd_param.encode())
        request_no = sha256(cmd_param_bytes).digest()

        # issue command
        pb = PubSub(self.app, Name.from_str('/putfile_client'))
        await pb.wait_for_ready()
        is_success = await pb.publish(Name.from_str(repo_name) + Name.from_str('insert'), cmd_param_bytes)
        assert is_success

        # insert_num should be (1, 1)
        checker = CommandChecker(self.app)
        n_retries = 5
        while n_retries > 0:
            response = await checker.check_insert(Name.from_str(repo_name), request_no)
            if response is None or response.status_code == RepoStatCode.NOT_FOUND:
                n_retries -= 1
            elif response.status_code != RepoStatCode.IN_PROGRESS:
                assert response.status_code == RepoStatCode.COMPLETED
                assert len(response.objs) == 2
                assert response.objs[0].insert_num == 1
                assert response.objs[1].insert_num == 1
                break
            await aio.sleep(1)

        # content should be 'foobar'
        _, _, content = await self.app.express_interest(Name.from_str('/test_foo/seg=0'))
        assert bytes(content).decode() == 'foo'
        _, _, content = await self.app.express_interest('/test_bar', can_be_prefix=True)
        assert bytes(content).decode() == 'bar'

        self.app.shutdown()


class TestLargeFile(RepoTestSuite):
    async def run(self):
        await aio.sleep(2)  # wait for repo to startup
        filepath1 = self.create_tmp_file(size_bytes=40*1024*1024)
        filepath2 = uuid.uuid4().hex.upper()[0:6]

        # put file
        pc = PutfileClient(self.app, Name.from_str('/putfile_client'), Name.from_str(repo_name))
        await pc.insert_file(filepath1, Name.from_str(filepath2), segment_size=8000,
                             freshness_period=0, cpu_count=multiprocessing.cpu_count())
        # get file
        gc = GetfileClient(self.app, Name.from_str(repo_name))
        await gc.fetch_file(Name.from_str(filepath2))
        # diff
        ret = filecmp.cmp(filepath1, filepath2)
        assert ret
        # cleanup
        self.files_to_cleanup.append(filepath1)
        self.files_to_cleanup.append(filepath2)
        self.app.shutdown()


class TestSingleDataInsert(RepoTestSuite):
    async def run(self):
        await aio.sleep(2)  # wait for repo to startup

        # respond to interest from repo
        def on_int(int_name, _int_param, _app_param):
            self.app.put_data(int_name, b'foobar', freshness_period=1000)
        await self.app.register('test_name', on_int)

        # construct insert parameter
        cmd_param = RepoCommandParam()
        cmd_obj = ObjParam()
        cmd_param.objs = [cmd_obj]
        cmd_obj.name = 'test_name'
        cmd_obj.forwarding_hint = None
        cmd_obj.start_block_id = None
        cmd_obj.end_block_id = None
        cmd_obj.register_prefix = None

        cmd_param_bytes = bytes(cmd_param.encode())
        request_no = sha256(cmd_param_bytes).digest()

        pb = PubSub(self.app, Name.from_str('/putfile_client'))
        await pb.wait_for_ready()
        is_success = await pb.publish(Name.from_str(repo_name) + Name.from_str('insert'), cmd_param_bytes)
        assert is_success

        # insert_num should be 1
        checker = CommandChecker(self.app)
        n_retries = 3
        while n_retries > 0:
            response = await checker.check_insert(Name.from_str(repo_name), request_no)
            if response is None or response.status_code == RepoStatCode.NOT_FOUND:
                n_retries -= 1
            elif response.status_code != RepoStatCode.IN_PROGRESS:
                assert response.status_code == RepoStatCode.COMPLETED
                assert len(response.objs) == 1
                assert response.objs[0].insert_num == 1
                break
            await aio.sleep(1)
        self.app.shutdown()


class TestFlags(RepoTestSuite):
    async def fetch(self, int_name, must_be_fresh, can_be_prefix):
        try:
            data_name, meta_info, content = await self.app.express_interest(
                int_name, must_be_fresh=must_be_fresh, can_be_prefix=can_be_prefix, lifetime=1000)
            return content
        except (InterestTimeout, InterestNack):
            return None

    async def run(self):
        await aio.sleep(1)  # wait for repo to startup

        filepath = self.create_tmp_file()
        filename = '/TestFlags/file'
        pc = PutfileClient(self.app, Name.from_str('/putfile_client'), Name.from_str(repo_name))
        await pc.insert_file(filepath, Name.from_str(filename), segment_size=8000,
                             freshness_period=0, cpu_count=multiprocessing.cpu_count())

        ret = await self.fetch(Name.from_str('/TestFlags'), must_be_fresh=False, can_be_prefix=False)
        assert ret is None
        ret = await self.fetch(Name.from_str('/TestFlags'), must_be_fresh=False, can_be_prefix=True)
        assert ret is not None
        ret = await self.fetch(Name.from_str('/TestFlags'), must_be_fresh=True, can_be_prefix=True)
        assert ret is None

        self.app.shutdown()


class TestNoneMetaInfo(RepoTestSuite):
    async def run(self):
        await aio.sleep(2)  # wait for repo to startup

        # respond to interest from repo
        def on_int(int_name, _int_param, _app_param):
            self.app.put_data(int_name, b'foobar', meta_info=None)
        await self.app.register('test_name', on_int)

        # construct insert parameter
        cmd_param = RepoCommandParam()
        cmd_obj = ObjParam()
        cmd_param.objs = [cmd_obj]
        cmd_obj.name = 'test_name'
        cmd_obj.forwarding_hint = None
        cmd_obj.start_block_id = None
        cmd_obj.end_block_id = None
        cmd_obj.register_prefix = None

        cmd_param_bytes = bytes(cmd_param.encode())
        request_no = sha256(cmd_param_bytes).digest()

        pb = PubSub(self.app, Name.from_str('/putfile_client'))
        await pb.wait_for_ready()
        is_success = await pb.publish(Name.from_str(repo_name) + Name.from_str('insert'), cmd_param_bytes)
        assert is_success

        # insert_num should be 1
        checker = CommandChecker(self.app)
        n_retries = 3
        while n_retries > 0:
            response = await checker.check_insert(Name.from_str(repo_name), request_no)
            if response is None or response.status_code == RepoStatCode.NOT_FOUND:
                n_retries -= 1
            elif response.status_code != RepoStatCode.IN_PROGRESS:
                assert response.status_code == RepoStatCode.COMPLETED
                assert len(response.objs) == 1
                assert response.objs[0].insert_num == 1
                break
            await aio.sleep(1)
        self.app.shutdown()


# Notes: The GitHub Actions failed this test case because of InterestNack.
#        However, we could not reproduce the failure.
#        Since we do not have sufficient understanding of the behavior, let
#        us temporarily abandon this test case.
#        We need to gain better knowledge on this in the future.
#
# class TestTcpBulkInsert(RepoTestSuite):
#     async def run(self):
#         await aio.sleep(2)  # wait for repo to startup
#
#         reader, writer = await aio.open_connection('127.0.0.1', port)
#
#         # insert data '/test/0'
#         writer.write(b'\x06?\x07\t\x08\x04test\x08\x010\x14\x03\x18\x01\x00\x15\x06foobar'
#                      b'\x16\x03\x1b\x01\x00\x17 \x94?\\\xae\x99\xd5\xd6\xa5\x18\xac\x00'
#                      b'\xe3\xcaX\x82\x972,\xf1\xebUQ\xa5I%\xb3\xd5\xac\xcc\xc6\x80Q')
#         writer.close()
#
#         # content should be 'foobar'
#         _, _, content = await self.app.express_interest(Name.from_str('/test/0'))
#         assert content.tobytes().decode() == 'foobar'
#         _, _, content = await self.app.express_interest('/test', can_be_prefix=True)
#         assert content.tobytes().decode() == 'foobar'
#         self.app.shutdown()
