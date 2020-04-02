import os
import pickle
import plyvel
from .storage_base import Storage
import time


class LevelDBStorage(Storage):
    def __init__(self, dir: str):
        db_dir = os.path.expanduser(dir)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir)
            except PermissionError:
                raise PermissionError(f'Could not create database directory: {db_path}') from None
        self.db = plyvel.DB(db_dir, create_if_missing=True)

    def _put(self, key: bytes, value: bytes, expire_time_ms: int=None):
        """
        Insert value and its expiration time into levelDB, overwrite if already exists.
        :param key: bytes.
        :param value: bytes.
        :param expire_time_ms: Optional[int]. Value is not fresh if expire_time_ms is not specified.
        """
        self.db.put(key, pickle.dumps((value, expire_time_ms)))

    def _get(self, key: bytes, can_be_prefix=False, must_be_fresh=False) -> bytes:
        """
        Get value from levelDB.
        :param key: bytes.
        :param can_be_prefix: bool.
        :param must_be_fresh: bool.
        :return: bytes.
        """
        if not can_be_prefix:
            record = self.db.get(key)
            if record == None:
                return None
            value, expire_time_ms = pickle.loads(record)
            if not must_be_fresh or expire_time_ms != None and expire_time_ms > int(time.time() * 1000):
                return value
            else:
                return None
        else:
            for _, v_e in self.db.iterator(prefix=key):
                value, expire_time_ms = pickle.loads(v_e)
                if not must_be_fresh or expire_time_ms != None and expire_time_ms > int(time.time() * 1000):
                    return value
            return None

    def _remove(self, key: bytes) -> bool:
        """
        Remove value from levelDB. Return whether removal is successful.
        :param key: bytes.
        :return: bool.
        """
        if self._get(key) != None:
            self.db.delete(key)
            return True
        else:
            return False