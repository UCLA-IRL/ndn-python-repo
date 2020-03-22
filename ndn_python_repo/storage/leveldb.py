import os
import plyvel
from .storage_base import Storage


class LevelDBStorage(Storage):
    def __init__(self, dir: str):
        db_dir = os.path.expanduser(dir)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir)
            except PermissionError:
                raise PermissionError(f'Could not create database directory: {db_path}') from None
        self.db = plyvel.DB(db_dir, create_if_missing=True)

    def put(self, key: bytes, value: bytes):
        self.db.put(key, value)

    def get(self, key: bytes, can_be_prefix=False, must_be_fresh=False) -> bytes:
        if not can_be_prefix:
            return self.db.get(key)
        else:
            pass

    def exists(self, key: bytes) -> bool:
        ret = self.db.get(key)
        return True if ret else False

    def remove(self, key: bytes) -> bool:
        if self.exists(key):
            self.db.delete(key)
            return True
        else:
            return False