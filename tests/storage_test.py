import abc
import os
import sys
from ndn.encoding import Name
from ndn_python_repo.storage import *
import pytest


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
        StorageTestFixture._test_get_data_packet()
        StorageTestFixture._test_freshness_period()
        StorageTestFixture._test_get_prefix()

    @staticmethod
    def _test_put():
        StorageTestFixture.storage._put(b'test_key_1', bytes([0x00, 0x01, 0x02, 0x03, 0x04]))

    @staticmethod
    def _test_get():
        b_in = bytes([0x00, 0x01, 0x02, 0x03, 0x04])
        StorageTestFixture.storage._put(b'test_key_1', b_in)
        b_out = StorageTestFixture.storage._get(b'test_key_1')
        assert b_in == b_out

    @staticmethod
    def _test_remove():
        StorageTestFixture.storage._put(b'test_key_1', bytes([0x00, 0x01, 0x02, 0x03, 0x04]))
        assert StorageTestFixture.storage._remove(b'test_key_1')
        assert StorageTestFixture.storage._remove(b'test_key_1') is False
    
    @staticmethod
    def _test_get_data_packet():
        # /test/0, freshnessPeriod = 10000ms
        data_bytes_in = b'\x06\xa2\x07#\x08\x14test_get_data_packet\x08\x010$\x08\x00\x00\x01q\x04\xa3%x\x14\x06\x18\x01\x00\x19\x01\x00\x15\rHello, world!\x16\x1c\x1b\x01\x03\x1c\x17\x07\x15\x08\x04test\x08\x03KEY\x08\x08\xa0\x04\xf7\xe7\xdd\x0f\x17\xbd\x17F0D\x02 P\xcc\r)\xa0\x9c\xc8\xf4E\xe9\xed\x83u\xb2\xfe\\ \xb1\x93\xbb\xbeq5\x18\x91\xd8yl\x96p\xc7\xa5\x02 Q\x07\xad!\xd3\xd5\xff\x07\xbewW~`*\xe9oI\xeb\x01\x12\xe7\xd0\xaf\xf3r\x95\x94q\xb5\xee\xdc\xc9'
        StorageTestFixture.storage.put_data_packet(Name.from_str('/test_get_data_packet/0'), data_bytes_in)
        data_bytes_out = StorageTestFixture.storage.get_data_packet(Name.from_str('/test_get_data_packet/0'))
        assert data_bytes_in == data_bytes_out
    
    @staticmethod
    def _test_freshness_period():
        # /test/0, freshnessPeriod = 0ms
        data_bytes_in = b'\x06\xa5\x07$\x08\x15test_freshness_period\x08\x010$\x08\x00\x00\x01q\x04\xa1\xd3\x1b\x14\x06\x18\x01\x00\x19\x01\x00\x15\rHello, world!\x16\x1c\x1b\x01\x03\x1c\x17\x07\x15\x08\x04test\x08\x03KEY\x08\x08\xa0\x04\xf7\xe7\xdd\x0f\x17\xbd\x17H0F\x02!\x00\xc2K\xb7\xa3z\xd5\xd6z\xe0RuX\xa8\x967\xca.\x81!\xb1)\x9a\xf1\xd8\xd8\xcd\x95\x16\xd6\xa9\xb7p\x02!\x00\xe1mb/|$\xc3\xbf\xd3\xb1\x8a\x97\xef\x84\xfe\xebI\x1b5e\xf4\x9f/\xd9\x0e\x9ae\xed7b\xdc/'
        StorageTestFixture.storage.put_data_packet(Name.from_str('/test_freshness_period/1'), data_bytes_in)
        data_bytes_out = StorageTestFixture.storage.get_data_packet(Name.from_str('/test_freshness_period/1'), 
            must_be_fresh=True)
        assert data_bytes_out == None
    
    @staticmethod
    def _test_get_prefix():
        # /test/0, freshnessPeriod = 10000ms
        data_bytes_in = b'\x06\x9d\x07\x1e\x08\x0ftest_get_prefix\x08\x010$\x08\x00\x00\x01q\x04\xa3u0\x14\x06\x18\x01\x00\x19\x01\x00\x15\rHello, world!\x16\x1c\x1b\x01\x03\x1c\x17\x07\x15\x08\x04test\x08\x03KEY\x08\x08\xa0\x04\xf7\xe7\xdd\x0f\x17\xbd\x17F0D\x02 L\x16\xe1\xb3v\x11r7"\xcaq<tY\xb0!\x1e\xac\xc0\xff?=l\x92w\xb6\x1b\xb7\xcdc\x11\x94\x02 \x01\x06p\xf3\x8cDg\xc5\x12^Y\xc0\xd2<\x0b\xbc\xbd\x05\xd0\xd0\xe5*%F\xbc\xd7y\x9bR\xc7f\x1a'
        StorageTestFixture.storage.put_data_packet(Name.from_str('/test_get_prefix/0'), data_bytes_in)
        data_bytes_out1 = StorageTestFixture.storage.get_data_packet(Name.from_str('/test_get_prefix'))
        data_bytes_out2 = StorageTestFixture.storage.get_data_packet(Name.from_str('/test_get_prefix'),
            can_be_prefix=True)
        data_bytes_out3 = StorageTestFixture.storage.get_data_packet(Name.from_str('/test_get_prefi'),
            can_be_prefix=True)
        assert data_bytes_out1 == None
        assert data_bytes_out2 == data_bytes_in
        assert data_bytes_out3 == None  # should be None because the last name component doesn't match


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