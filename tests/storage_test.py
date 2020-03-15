import os
import sys
import abc
import pytest
from ndn_python_repo.storage import *


class StorageTestFixture(object):
    """
    Abstract test cases for all storage types.
    """
    storage = None

    @staticmethod
    def test_main():
        StorageTestFixture._test_put()
        StorageTestFixture._test_get()
        StorageTestFixture._test_remove()
        StorageTestFixture._test_exists()

    @staticmethod
    def _test_put():
        StorageTestFixture.storage.put(b'test_key_1', bytes([0x00, 0x01, 0x02, 0x03, 0x04]))

    @staticmethod
    def _test_get():
        b_in = bytes([0x00, 0x01, 0x02, 0x03, 0x04])
        StorageTestFixture.storage.put(b'test_key_1', b_in)
        b_out = StorageTestFixture.storage.get(b'test_key_1')
        assert b_in == b_out

    @staticmethod
    def _test_remove():
        StorageTestFixture.storage.put(b'test_key_1', bytes([0x00, 0x01, 0x02, 0x03, 0x04]))
        assert StorageTestFixture.storage.remove(b'test_key_1')
        assert StorageTestFixture.storage.remove(b'test_key_1') is False

    @staticmethod
    def _test_exists():
        StorageTestFixture.storage.remove(b'test_key_1')
        StorageTestFixture.storage.remove(b'test_key_2')
        StorageTestFixture.storage.put(b'test_key_1', bytes([0x00, 0x01, 0x02, 0x03, 0x04]))
        assert StorageTestFixture.storage.exists(b'test_key_1')
        assert StorageTestFixture.storage.exists(b'test_key_2') is False


# Default DB is SQLite
class TestSqliteStorage(StorageTestFixture):
    """
    Test SqliteStorage
    """
    @staticmethod
    def test_main(tmp_path):
        StorageTestFixture.storage = SqliteStorage(tmp_path / "test.db")
        StorageTestFixture.test_main()

# Unit tests for optional DBs only if they can be successfully imported
class TestLevelDBStorage(StorageTestFixture):
    """
    Test MongoDBStorage
    """
    @staticmethod
    def test_main(tmp_path):
        try:
            from ndn_python_repo.storage import LevelDBStorage
        except ImportError as exc:
            return
        StorageTestFixture.storage = LevelDBStorage(tmp_path)
        StorageTestFixture.test_main()

class TestMongoDBStorage(StorageTestFixture):
    """
    Test MongoDBStorage
    """
    @staticmethod
    def test_main(tmp_path):
        try:
            from ndn_python_repo.storage import MongoDBStorage
        except ImportError as exc:
            return
        StorageTestFixture.storage = MongoDBStorage('_test_db', '_test_collection')
        StorageTestFixture.test_main()