import asyncio as aio
import filecmp
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ndn_python_repo.clients import GetfileClient
from ndn_python_repo.clients import PutfileClient
import os
import pytest
import subprocess
import tempfile
import uuid


inline_cfg = """
---
repo_config:
  repo_name: 'testrepo'
db_config:
  db_type: 'sqlite3'
  sqlite3:
    'path': '~/.ndn/ndn-python-repo/sqlite3_test.db'
  leveldb:
    'dir': '~/.ndn/ndn-python-repo/leveldb_test/'
  mongodb:
    'db': 'repo_test'
    'collection': 'data'
tcp_bulk_insert:
  'addr': '0.0.0.0'
  'port': '7376'
"""


class RepoTestSuite(object):

    def test_main(self):
        self.startup()
        self.cleanup()

    def startup(self):
        self.files_to_cleanup = []

        tmp_cfg_path = self.create_tmp_cfg()
        self.files_to_cleanup.append(tmp_cfg_path)
        self.repo_proc = subprocess.Popen(['ndn-python-repo', '-c', tmp_cfg_path])
        
        self.app = NDNApp(face=None, keychain=KeychainDigest())
        self.app.run_forever(after_start=self.run())

    def cleanup(self):
        self.repo_proc.kill()
        for file in self.files_to_cleanup:
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
        print('Tmp cfg:', tmp_cfg_path)
        return tmp_cfg_path

    async def run(self):
        pass


class TestBasic(RepoTestSuite):
    async def run(self):
        await aio.sleep(1)  # wait for repo to startup

        filepath1 = self.create_tmp_file()
        filepath2 = uuid.uuid4().hex.upper()[0:6]
        
        # put
        pc = PutfileClient(self.app, Name.from_str('/testrepo'))
        await pc.insert_file(filepath1, Name.from_str(filepath2))
        # get
        gc = GetfileClient(self.app, Name.from_str('/testrepo'))
        await gc.fetch_file(Name.from_str(filepath2))
        # diff
        ret = filecmp.cmp(filepath1, filepath2)
        print("Is same: ", ret)
        # cleanup
        self.files_to_cleanup.append(filepath1)
        self.files_to_cleanup.append(filepath2)
        self.app.shutdown()


class TestLargeFile(RepoTestSuite):
    async def run(self):
        filepath1 = self.create_tmp_file(size_bytes=40*1024*1024)
        filepath2 = uuid.uuid4().hex.upper()[0:6]
        
        # put file
        pc = PutfileClient(self.app, Name.from_str('/testrepo'))
        await pc.insert_file(filepath1, Name.from_str(filepath2))

        # get file
        gc = GetfileClient(self.app, Name.from_str('/testrepo'))
        await gc.fetch_file(Name.from_str(filepath2))

        # diff
        ret = filecmp.cmp(filepath1, filepath2)
        print("Is same: ", ret)

        # cleanup
        self.files_to_cleanup.append(filepath1)
        self.files_to_cleanup.append(filepath2)
        self.app.shutdown()


if __name__ == '__main__':
    TestBasic().test_main()
    # TestLargeFile().test_main()