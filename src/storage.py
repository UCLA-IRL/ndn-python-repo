import os
import sys
import pymongo
from pymongo import MongoClient
import plyvel

class Storage:
    """
    Interface for storage functionalities
    """
    def put(self, key: str, data: bytes):
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def remove(self, key: str) -> bool:
        raise NotImplementedError

default_leveldb_dir = "~/.py-ndn-repo/"

class LevelDBStorage(Storage):
    def __init__(self, dir: str):
        db_dir = os.path.expanduser(dir)
        self.db = plyvel.DB(db_dir, create_if_missing=True)

    def put(self, key: str, value: bytes):
        self.db.put(key.encode(), value)

    def get(self, key: str) -> bytes:
        return self.db.get(key.encode())

    def exists(self, key: str) -> bool:
        ret = self.db.get(key.encode())
        if ret:
            return True
        else:
            return False

    def remove(self, key: str) -> bool:
        self.db.delete(key.encode())
        return True

class MongoDBStorage(Storage):
    def __init__(self, db: str, collection: str):
        """
        Init DB with unique index on hash
        """
        self._db = db
        self._collection = collection
        self._uri = 'mongodb://localhost:27017/'
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

    def get(self, key: str) -> bytes:
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

    def keys(self):
        """
        Return a set of "primary" keys
        """
        return (doc["key"] for doc in self.c_collection.find())


# For testing
if __name__ == "__main__":
    # s = MongoDBStorage("gitsync", "objects")
    # hash_name = "cf23df2207d99a74fbe169e3eba035e633b65d94"
    # data = b'\x01\x02\x03\x04\x05'
    # s.put(hash_name, data)
    s = LevelDBStorage()
    hash_name = "cf23df2207d99a74fbe169e3eba035e633b65d94"
    data = b'\x01\x02\x03\x04\x05'
    s.put(hash_name, data)