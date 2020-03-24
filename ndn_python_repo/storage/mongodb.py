import base64
import pymongo
from pymongo import MongoClient
from .storage_base import Storage
import time
from typing import List, Optional


class MongoDBStorage(Storage):

    def __init__(self, db: str, collection: str):
        """
        Init DB with unique index on key.
        """
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
        Insert document into MongoDB, overwrite if already exists. MongoDB supports prefix search 
        only on strings, so keys are stored in base16 format.
        Base32 and base64 dont't work here, because they don't preserve prefix search semantics.
        :param key: bytes.
        :param value: bytes.
        :param expire_time_ms: Optional[int]. Value is not fresh if expire_time_ms is not specified.
        """
        key = base64.b16encode(key).decode()
        document = {
            'key': key,
            'value': value,
            'expire_time_ms': expire_time_ms
        }
        try:
            self.c_collection.insert_one(document).inserted_id
        except pymongo.errors.DuplicateKeyError:
            self.c_collection.update_one({'key': key}, 
                {'$set': {'value': value, 'expire_time_ms': expire_time_ms}})

    def _get(self, key: bytes, can_be_prefix=False, must_be_fresh=False) -> Optional[bytes]:
        """
        Get document from MongoDB.
        :param key: bytes.
        :param can_be_prefix: bool. 
        :param must_be_fresh: bool.
        :return: bytes.
        """
        key = base64.b16encode(key).decode()
        query = dict()
        if not can_be_prefix:
            query.update({'key': key})
        else:
            query.update({'key': {'$regex': '^' + key}})
        if must_be_fresh:
            query.update({'expire_time_ms': {'$gt': int(time.time() * 1000)}})
        ret = self.c_collection.find_one(query)
        if ret:
            return ret['value']
        else:
            return None

    def _remove(self, key: bytes) -> bool:
        """
        Remove value from MongoDB, return whether removal is successful.
        :param key: bytes.
        :return: bool.
        """
        key = base64.b16encode(key).decode()
        return self.c_collection.delete_one({"key": key}).deleted_count > 0