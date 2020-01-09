import os
import plyvel
from .storage_base import Storage


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
        return True if ret else False

    def remove(self, key: str) -> bool:
        self.db.delete(key.encode())
        return True

    def get_key_list(self) -> list:
        key_list = list()
        for key, value in self.db:
            key_list.append(key.decode())
        return key_list
