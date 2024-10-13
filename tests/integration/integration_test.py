import asyncio as aio
import filecmp
import multiprocessing
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ndn.types import InterestNack, InterestTimeout
from ndn_python_repo.clients import GetfileClient, PutfileClient, DeleteClient, CommandChecker
from ndn_python_repo.command import RepoCommandParam, ObjParam, RepoStatCode
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
