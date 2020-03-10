import asyncio as aio
import filecmp
from ndn.app import NDNApp
from ndn.encoding import Name, Component
from ndn.security import KeychainDigest
from ndn_python_repo.clients import GetfileClient, PutfileClient, CommandChecker
from ndn_python_repo.command.repo_commands import RepoCommandParameter, RepoCommandResponse
import os
import platform
import pytest
import subprocess
import tempfile
import uuid


sqlite3_path = os.path.join(tempfile.mkdtemp(), 'sqlite3_test.db')
repo_name = 'testrepo'
inline_cfg = f"""
---
repo_config:
  repo_name: '{repo_name}'
db_config:
  db_type: 'sqlite3'
  sqlite3:
    'path': '{sqlite3_path}'
tcp_bulk_insert:
  'addr': '0.0.0.0'
  'port': '7377'
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
        await aio.sleep(1)  # wait for repo to startup
        filepath1 = self.create_tmp_file()
        filepath2 = uuid.uuid4().hex.upper()[0:6]
        
        # put
        pc = PutfileClient(self.app, Name.from_str(repo_name))
        await pc.insert_file(filepath1, Name.from_str(filepath2))
        # get
        gc = GetfileClient(self.app, Name.from_str(repo_name))
        await gc.fetch_file(Name.from_str(filepath2))
        # diff
        ret = filecmp.cmp(filepath1, filepath2)
        print("Is same: ", ret)
        assert ret
        # cleanup
        self.files_to_cleanup.append(filepath1)
        self.files_to_cleanup.append(filepath2)
        self.app.shutdown()


class TestLargeFile(RepoTestSuite):
    async def run(self):
        await aio.sleep(1)  # wait for repo to startup
        filepath1 = self.create_tmp_file(size_bytes=40*1024*1024)
        filepath2 = uuid.uuid4().hex.upper()[0:6]
        
        # put file
        pc = PutfileClient(self.app, Name.from_str(repo_name))
        await pc.insert_file(filepath1, Name.from_str(filepath2))
        # get file
        gc = GetfileClient(self.app, Name.from_str(repo_name))
        await gc.fetch_file(Name.from_str(filepath2))
        # diff
        ret = filecmp.cmp(filepath1, filepath2)
        print("Is same: ", ret)
        assert ret
        # cleanup
        self.files_to_cleanup.append(filepath1)
        self.files_to_cleanup.append(filepath2)
        self.app.shutdown()


class TestInvalidParam(RepoTestSuite):
    async def run(self):
        await aio.sleep(1)  # wait for repo to startup

        # build an invalid param
        cmd_param = RepoCommandParameter()
        cmd_param.name = 'test_name'
        cmd_param.start_block_id = None
        cmd_param.end_block_id = 10
        cmd_param_bytes = cmd_param.encode()
        name = Name.from_str(repo_name)
        name.append('insert')
        name.append(Component.from_bytes(cmd_param_bytes))

        # should return status code 403
        try:
            data_name, meta_info, content = await self.app.express_interest(
                name, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
        except InterestNack as e:
            logging.warning(f'Nacked with reason: {e.reason}')
            return
        except InterestTimeout:
            logging.warning(f'Timeout')
            return
        try:
            cmd_response = RepoCommandResponse.parse(content)
        except DecodeError as exc:
            logging.warning('Response blob decoding failed')
            return
        assert cmd_response.status_code == 403
        self.app.shutdown()


class TestSingleDataInsert(RepoTestSuite):
    async def run(self):
        await aio.sleep(1)  # wait for repo to startup
        
        cmd_param = RepoCommandParameter()
        cmd_param.name = 'test_name'
        cmd_param.start_block_id = None
        cmd_param.end_block_id = None
        cmd_param_bytes = cmd_param.encode()
        name = Name.from_str(repo_name)
        name.append('insert')
        name.append(Component.from_bytes(cmd_param_bytes))

        # respond to interest from repo
        def on_int(int_name, _int_param, _app_param):
            print('Test program receive interest')
            self.app.put_data(int_name, b'foobar', freshness_period=1000)
        await self.app.register('test_name', on_int)

        # should return status code 200, insert_num 1
        try:
            data_name, meta_info, content = await self.app.express_interest(
                name, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
        except InterestNack as e:
            logging.warning(f'Nacked with reason: {e.reason}')
            return
        except InterestTimeout:
            logging.warning(f'Timeout')
            return
        try:
            cmd_response = RepoCommandResponse.parse(content)
        except DecodeError as exc:
            logging.warning('Response blob decoding failed')
            return
        process_id = cmd_response.process_id
        
        # insert_num should be 1
        checker = CommandChecker(self.app)
        while True:
            response = await checker.check_insert(Name.from_str(repo_name), process_id)
            if response.status_code != 300:
                assert response.status_code == 200
                assert response.insert_num == 1
                break
            await aio.sleep(1)
        self.app.shutdown()


if __name__ == '__main__':
    TestBasic().test_main()
    TestLargeFile().test_main()
    TestInvalidParam().test_main()
    TestSingleDataInsert().test_main()