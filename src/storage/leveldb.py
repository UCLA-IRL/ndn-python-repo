import os
import sys
import plyvel
from . import Storage

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