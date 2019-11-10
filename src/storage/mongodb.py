import pymongo
from pymongo import MongoClient
from typing import List, Optional
from .storage_base import Storage


class MongoDBStorage(Storage):
    def __init__(self, db: str, collection: str):
        """
        Init DB with unique index on key
        """
        self._db = db
        self._collection = collection
        self._uri = 'mongodb://127.0.0.1:27017/'
        self.client = MongoClient(self._uri)
        self.c_db = self.client[self._db]
        self.c_collection = self.c_db[self._collection]

        client = MongoClient(self._uri)
        c_db = client[self._db]
        c_collection = c_db[self._collection]
        c_collection.create_index('key', unique=True)

    def put(self, key: str, value: bytes):
        """
        Insert document into MongoDB, overwrite if already exists.
        """
        document = {
            "key": key,
            "value": value
        }
        try:
            self.c_collection.insert_one(document).inserted_id
        except pymongo.errors.DuplicateKeyError:
            self.c_collection.update_one({"key": key}, {"$set": {"value": value}})

    def get(self, key: str) -> Optional[bytes]:
        """
        Get document from MongoDB
        """
        ret = self.c_collection.find_one({"key": key})
        if ret:
            return ret["value"]
        else:
            return None

    def exists(self, key: str) -> bool:
        """
        Return whether document exists
        """
        if self.c_collection.find_one({"key": key}):
            return True
        else:
            return False

    def remove(self, key: str) -> bool:
        """
        Return whether removal is successful
        """
        return self.c_collection.delete_one({"key": key}).deleted_count > 0

    def keys(self) -> List[str]:
        """
        Return a set of "primary" keys
        """
        return (doc["key"] for doc in self.c_collection.find())