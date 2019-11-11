import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import abc
import pytest
from src.storage import *


class StorageTestFixture(object):
    """
    Abstract test cases for all storage types.
    """
    storage = None

    @staticmethod
    def test_main():
        StorageTestFixture._test_put()
        StorageTestFixture._test_get()
        StorageTestFixture.__test_remove()
        StorageTestFixture._test_exists()

    @staticmethod
    def _test_put():
        StorageTestFixture.storage.put('test_key_1', bytes([0x00, 0x01, 0x02, 0x03, 0x04]))

    @staticmethod
    def _test_get():
        b_in = bytes([0x00, 0x01, 0x02, 0x03, 0x04])
        StorageTestFixture.storage.put('test_key_1', b_in)
        b_out = StorageTestFixture.storage.get('test_key_1')
        assert b_in == b_out

    @staticmethod
    def __test_remove():
        StorageTestFixture.storage.put('test_key_1', bytes([0x00, 0x01, 0x02, 0x03, 0x04]))
        assert StorageTestFixture.storage.remove('test_key_1')
        assert StorageTestFixture.storage.remove('test_key_1') is False

    @staticmethod
    def _test_exists():
        StorageTestFixture.storage.remove('test_key_1')
        StorageTestFixture.storage.remove('test_key_2')
        StorageTestFixture.storage.put('test_key_1', bytes([0x00, 0x01, 0x02, 0x03, 0x04]))
        assert StorageTestFixture.storage.exists('test_key_1')
        assert StorageTestFixture.storage.exists('test_key_2') is False


# Default DB is SQLite
class TestSqliteStorage(StorageTestFixture):
    """
    Test SqliteStorage
    """
    @staticmethod
    def test_main():
        StorageTestFixture.storage = SqliteStorage()
        StorageTestFixture.test_main()


try:
    from src.storage import MongoDBStorage

    class TestMongoDBStorage(StorageTestFixture):
        """
        Test MongoDBStorage
        """
        @staticmethod
        def test_main():
            StorageTestFixture.storage = SqliteStorage()
            StorageTestFixture.test_main()

except ImportError as exc:
    pass