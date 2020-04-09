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
        StorageTestFixture._test_put_batch()
        StorageTestFixture._test_write_back()

    @staticmethod
    def _test_put():
        StorageTestFixture.storage._put(b'test_key_1', bytes([0x00, 0x01, 0x02, 0x03, 0x04]))
    
    @staticmethod
    def _test_duplicate_put():
        StorageTestFixture.storage._put(b'test_key_1', bytes([0x00, 0x01, 0x02, 0x03, 0x04]))
        StorageTestFixture.storage._put(b'test_key_1', bytes([0x05, 0x06, 0x07, 0x08, 0x09]))
        b_out = StorageTestFixture.storage._get(b'test_key_1')
        assert b_out == bytes([0x05, 0x06, 0x07, 0x08, 0x09])

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
        # /test_get_data_packet/0, freshnessPeriod = 10000ms
        data_bytes_in = b'\x06\xa2\x07#\x08\x14test_get_data_packet\x08\x010$\x08\x00\x00\x01q\x04\xa3%x\x14\x06\x18\x01\x00\x19\x01\x00\x15\rHello, world!\x16\x1c\x1b\x01\x03\x1c\x17\x07\x15\x08\x04test\x08\x03KEY\x08\x08\xa0\x04\xf7\xe7\xdd\x0f\x17\xbd\x17F0D\x02 P\xcc\r)\xa0\x9c\xc8\xf4E\xe9\xed\x83u\xb2\xfe\\ \xb1\x93\xbb\xbeq5\x18\x91\xd8yl\x96p\xc7\xa5\x02 Q\x07\xad!\xd3\xd5\xff\x07\xbewW~`*\xe9oI\xeb\x01\x12\xe7\xd0\xaf\xf3r\x95\x94q\xb5\xee\xdc\xc9'
        StorageTestFixture.storage.put_data_packet(Name.from_str('/test_get_data_packet/0'), data_bytes_in)
        data_bytes_out = StorageTestFixture.storage.get_data_packet(Name.from_str('/test_get_data_packet/0'))
        assert data_bytes_in == data_bytes_out
    
    @staticmethod
    def _test_freshness_period():
        # /test_freshness_period/0, freshnessPeriod = 0ms
        data_bytes_in = b'\x06\xa5\x07$\x08\x15test_freshness_period\x08\x010$\x08\x00\x00\x01q\x04\xa1\xd3\x1b\x14\x06\x18\x01\x00\x19\x01\x00\x15\rHello, world!\x16\x1c\x1b\x01\x03\x1c\x17\x07\x15\x08\x04test\x08\x03KEY\x08\x08\xa0\x04\xf7\xe7\xdd\x0f\x17\xbd\x17H0F\x02!\x00\xc2K\xb7\xa3z\xd5\xd6z\xe0RuX\xa8\x967\xca.\x81!\xb1)\x9a\xf1\xd8\xd8\xcd\x95\x16\xd6\xa9\xb7p\x02!\x00\xe1mb/|$\xc3\xbf\xd3\xb1\x8a\x97\xef\x84\xfe\xebI\x1b5e\xf4\x9f/\xd9\x0e\x9ae\xed7b\xdc/'
        StorageTestFixture.storage.put_data_packet(Name.from_str('/test_freshness_period/1'), data_bytes_in)
        data_bytes_out = StorageTestFixture.storage.get_data_packet(Name.from_str('/test_freshness_period/1'), 
            must_be_fresh=True)
        assert data_bytes_out == None
    
    @staticmethod
    def _test_get_prefix():
        # /test_get_prefix/0, freshnessPeriod = 10000ms
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
    
    @staticmethod
    def _test_put_batch():
        keys = [b'/test_put_batch0', b'/test_put_batch1', b'/test_put_batch2']
        values = [
            b"\x06\x92\x07\x11\x08\x0ftest_put_batch0\x14\x07\x18\x01\x00\x19\x02'\x10\x15\rHello, world!\x16\x1c\x1b\x01\x03\x1c\x17\x07\x15\x08\x04test\x08\x03KEY\x08\x08\xa0\x04\xf7\xe7\xdd\x0f\x17\xbd\x17G0E\x02 x\xd8\xc0\xd6\xbbe\xde7\xb3\x8c\xa5\x94\x9a87\xf9@xb=:zlqY\xca\xfaj\xa0^\x03\x7f\x02!\x00\xff\x06\x08E\x86\x1d@\x80'\xffv>\x906\xc1X\xb1N\x168uH\xcb\x18r\x8d\xafHi\x1e\x7fZ",
            b'\x06\x91\x07\x11\x08\x0ftest_put_batch1\x14\x07\x18\x01\x00\x19\x02\'\x10\x15\rHello, world!\x16\x1c\x1b\x01\x03\x1c\x17\x07\x15\x08\x04test\x08\x03KEY\x08\x08\xa0\x04\xf7\xe7\xdd\x0f\x17\xbd\x17F0D\x02 2xY\xdb\xa5[\t\x1cxS\xdb$<N"e\x08\xd5\x1f<\x95\xe6\xd0\x01\xa8vaW^\x8c$,\x02 \x0bg\x0b\xfeW\x91\xe1\xa62\x0b$\xe9\x85\xdaW\x06\xeaI\xb1+\xc5A\xb8\xa1\xaf\xded6\x17N27',
            b'\x06\x93\x07\x11\x08\x0ftest_put_batch2\x14\x07\x18\x01\x00\x19\x02\'\x10\x15\rHello, world!\x16\x1c\x1b\x01\x03\x1c\x17\x07\x15\x08\x04test\x08\x03KEY\x08\x08\xa0\x04\xf7\xe7\xdd\x0f\x17\xbd\x17H0F\x02!\x00\x91\xab\xe8\x12\xb9\nD\x02\xaaJ\xe2B~tz\xc5\x86\x91\xc8:\xb6\xe4[b\x14\xfc\x9d}\xe5Qg\xb4\x02!\x00\x86\xc1\\\x8e\xd6\x9e\xf5\xa9\xe8t\xe4\x1f\xcb\xb6\xe6v\xc8,9\x1b\xdfO;\x0cl\xc4"]\x91\x10\xca\xdc'
        ]
        StorageTestFixture.storage._put(keys[0], b'should be overwritten')
        StorageTestFixture.storage._put_batch(keys, values, [None] * len(keys))
        assert StorageTestFixture.storage._get(keys[0]) == values[0]
        assert StorageTestFixture.storage._get(keys[1]) == values[1]
        assert StorageTestFixture.storage._get(keys[2]) == values[2]
    
    @staticmethod
    def _test_write_back():
        # /test_write_back/0
        data_bytes_in = b'\x06\x94\x07\x14\x08\x0ftest_write_back\x08\x010\x14\x07\x18\x01\x00\x19\x02\'\x10\x15\rHello, world!\x16\x1c\x1b\x01\x03\x1c\x17\x07\x15\x08\x04test\x08\x03KEY\x08\x08\xa0\x04\xf7\xe7\xdd\x0f\x17\xbd\x17F0D\x02 Qbu1~\xf7f\xe8\xa0\x19\xa8F\xa5*\xbe\xef"\xb0p\xd5\x1ei%J\xaf\xe8s\x8bcH\x85`\x02 <\xb3:7\x1e0\xfc\x15\x96r:\xacWAHZ\x939\x9f^\x12\x1a\x8cl\xcc\x01C\xfe\xbf\x87\x0b\x1a'
        StorageTestFixture.storage.put_data_packet(Name.from_str('/test_write_back/0'), data_bytes_in)
        StorageTestFixture.storage._write_back()
        data_bytes_out = StorageTestFixture.storage.get_data_packet(Name.from_str('/test_write_back/0'))
        assert data_bytes_in == data_bytes_out


# Default DB is SQLite
class TestSqliteStorage(StorageTestFixture):
    """
    Test SqliteStorage
    """
    @staticmethod
    def test_main(tmp_path):
        StorageTestFixture.storage = SqliteStorage(tmp_path / 'test.db')
        StorageTestFixture.test_main()

# Unit tests for optional DBs only if they can be successfully imported
class TestLevelDBStorage(StorageTestFixture):
    """
    Test LevelDBStorage
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