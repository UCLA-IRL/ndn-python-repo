import asyncio as aio
import filecmp
import logging
import multiprocessing
from ndn.app import NDNApp
from ndn.encoding import Name, Component
from ndn.security import KeychainDigest
from ndn.types import InterestNack, InterestTimeout
from ndn.utils import gen_nonce
from ndn_python_repo.clients import GetfileClient, PutfileClient, DeleteClient, CommandChecker
from ndn_python_repo.command.repo_commands import RepoCommandParameter, RepoCommandResponse, CheckPrefix
from ndn_python_repo.utils import PubSub
import os
import platform
import pytest
import subprocess
import tempfile
import uuid


sqlite3_path = os.path.join(tempfile.mkdtemp(), 'sqlite3_test.db')
repo_name = 'testrepo'
register_root = False
port = 7377
inline_cfg = f"""
---
repo_config:
  repo_name: '{repo_name}'
  register_root: {register_root}
db_config:
  db_type: 'sqlite3'
  sqlite3:
    'path': '{sqlite3_path}'
tcp_bulk_insert:
  addr: '0.0.0.0'
  port: '{port}'
  register_prefix: True
  prefixes:
  - /test
logging_config:
  level: 'INFO' 
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

    def create_tmp_file(self, size_bytes=4096):
        tmp_file_path = os.path.join(tempfile.mkdtemp(), 'tempfile')
        with open(tmp_file_path, 'wb') as f:
            f.write(os.urandom(size_bytes))
        return tmp_file_path

    def create_tmp_cfg(self):
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
        cmd_param = RepoCommandParameter()
        cmd_param.name = 'test_name'
        cmd_param.start_block_id = None
        cmd_param.end_block_id = None
        process_id = os.urandom(4)
        cmd_param.process_id = process_id
        cmd_param.check_prefix = CheckPrefix()
        cmd_param.check_prefix.name = Name.from_str('/putfile_client')
        cmd_param_bytes = cmd_param.encode()

        pb = PubSub(self.app, Name.from_str('/putfile_client'))
        await pb.wait_for_ready()
        is_success = await pb.publish(Name.from_str(repo_name) + ['insert'], cmd_param_bytes)
        assert is_success

        # insert_num should be 1
        checker = CommandChecker(self.app)
        n_retries = 3
        while n_retries > 0:
            response = await checker.check_insert(Name.from_str(repo_name), process_id)
            if response is None or response.status_code == 404:
                n_retries -= 1
            elif response.status_code != 300:
                assert response.status_code == 200
                assert response.insert_num == 1
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


# Notes: The Github Actions failed this test case because of InterestNack.
#        However we could not reproduce the failure.
#        Since we do not have sufficient understanding of the behavior, let
#        us temporarily abandon this test case.
#        We need to gain better knowledge on this in future.
#
# class TestTcpBulkInsert(RepoTestSuite):
#     async def run(self):
#         await aio.sleep(2)  # wait for repo to startup

#         reader, writer = await aio.open_connection('127.0.0.1', port)

#         # insert data '/test/0'
#         writer.write(b'\x06?\x07\t\x08\x04test\x08\x010\x14\x03\x18\x01\x00\x15\x06foobar'
#                      b'\x16\x03\x1b\x01\x00\x17 \x94?\\\xae\x99\xd5\xd6\xa5\x18\xac\x00'
#                      b'\xe3\xcaX\x82\x972,\xf1\xebUQ\xa5I%\xb3\xd5\xac\xcc\xc6\x80Q')
#         writer.close()

#         # content should be 'foobar'
#         _, _, content = await self.app.express_interest(Name.from_str('/test/0'))
#         assert content.tobytes().decode() == 'foobar'
#         _, _, content = await self.app.express_interest('/test', can_be_prefix=True)
#         assert content.tobytes().decode() == 'foobar'
#         self.app.shutdown()
