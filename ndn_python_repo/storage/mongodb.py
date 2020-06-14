import base64
import pymongo
from pymongo import MongoClient, ReplaceOne
from .storage_base import Storage
from typing import List, Optional


class MongoDBStorage(Storage):

    def __init__(self, db: str, collection: str):
        """
        Init a MongoDB storage with unique index on key.

        :param db: str. Database name.
        :param collection: str. Collection name.
        """
        super().__init__()
        self._db = db
        self._collection = collection
        self._uri = 'mongodb://127.0.0.1:27017/'
        self.client = MongoClient(self._uri)
        self.c_db = self.client[self._db]
        self.c_collection = self.c_db[self._collection]

        client = MongoClient(self._uri)
        client.server_info()    # will throw an exception if not connected
        c_db = client[self._db]
        c_collection = c_db[self._collection]
        c_collection.create_index('key', unique=True)

    def _put(self, key: bytes, value: bytes, expire_time_ms: int=None):
        """
        Insert document into MongoDB, overwrite if already exists. MongoDB supports prefix search\
            only on strings, so keys are stored in base16 format.
        Base32 and base64 don't work here, because they don't preserve prefix search semantics.

        :param key: bytes.
        :param value: bytes.
        :param expire_time_ms: Optional[int]. This data is marked unfresh after ``expire_time_ms``\
            milliseconds.
        """
        key = base64.b16encode(key).decode()
        replace = {
            'key': key,
            'value': value,
            'expire_time_ms': expire_time_ms,
        }
        self.c_collection.replace_one({'key': key}, replace, upsert=True)

    def _put_batch(self, keys: List[bytes], values: List[bytes], expire_time_mss:List[Optional[int]]):
        """
        Batch insert.

        :param key: List[bytes].
        :param value: List[bytes].
        :param expire_time_ms: List[Optional[int]]. The expiration time for each data in ``value``.
        """
        keys = [base64.b16encode(key).decode() for key in keys]
        replaces = []
        for key, value, expire_time_ms in zip(keys, values, expire_time_mss):
            replaces.append(ReplaceOne({'key': key}, {
                'key': key,
                'value': value,
                'expire_time_ms': expire_time_ms,
            }, upsert=True))
        self.c_collection.bulk_write(replaces, ordered=False)

    def _get(self, key: bytes, can_be_prefix=False, must_be_fresh=False) -> Optional[bytes]:
        """
        Get document from MongoDB.

        :param key: bytes.
        :param can_be_prefix: bool. If true, use prefix match instead of exact match.
        :param must_be_fresh: bool. If true, ignore expired data.
        :return: The value of the data packet.
        """
        key = base64.b16encode(key).decode()
        query = dict()
        if not can_be_prefix:
            query.update({'key': key})
        else:
            query.update({'key': {'$regex': '^' + key}})
        if must_be_fresh:
            query.update({'expire_time_ms': {'$gt': self.time_ms()}})
        ret = self.c_collection.find_one(query)
        if ret:
            return ret['value']
        else:
            return None

    def _remove(self, key: bytes) -> bool:
        """
        Remove value from MongoDB, return whether removal is successful.

        :param key: bytes.
        :return: True if a data packet is being removed.
        """
        key = base64.b16encode(key).decode()
        return self.c_collection.delete_one({"key": key}).deleted_count > 0