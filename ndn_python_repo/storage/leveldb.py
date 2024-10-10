import os
import pickle
import plyvel # fixme: my ide tells me this doesn't exist
from .storage_base import Storage
from typing import Optional


class LevelDBStorage(Storage):

    def __init__(self, level_dir: str):
        """
        Creates a LevelDB storage instance at disk location ``str``.

        :param level_dir: str. The disk location of the database directory.
        """
        super().__init__()
        db_dir = os.path.expanduser(level_dir)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir)
            except PermissionError:
                raise PermissionError(f'Could not create database directory: {db_dir}') from None
        self.db = plyvel.DB(db_dir, create_if_missing=True)

    def _put(self, key: bytes, value: bytes, expire_time_ms: int=None):
        """
        Insert value and its expiration time into levelDB, overwrite if already exists.

        :param key: bytes.
        :param value: bytes.
        :param expire_time_ms: Optional[int]. This data is marked unfresh after ``expire_time_ms``\
            milliseconds.
        """
        self.db.put(key, pickle.dumps((value, expire_time_ms)))

    def _put_batch(self, keys: list[bytes], values: list[bytes], expire_time_mss:list[Optional[int]]):
        """
        Batch insert.

        :param keys: list[bytes].
        :param values: list[bytes].
        :param expire_time_mss: list[Optional[int]]. The expiration time for each data in ``value``.
        """
        with self.db.write_batch() as b:
            for key, value, expire_time_ms in zip(keys, values, expire_time_mss):
                b.put(key, pickle.dumps((value, expire_time_ms)))

    def _get(self, key: bytes, can_be_prefix=False, must_be_fresh=False) -> bytes | None:
        """
        Get value from levelDB.

        :param key: bytes.
        :param can_be_prefix: bool. If true, use prefix match instead of exact match.
        :param must_be_fresh: bool. If true, ignore expired data.
        :return: bytes. The value of the data packet in bytes or None if it can't be found or is not fresh when must_be_fresh is True.
        """
        if not can_be_prefix:
            record = self.db.get(key)
            if record is None:
                return None
            value, expire_time_ms = pickle.loads(record)
            if not must_be_fresh or expire_time_ms is not None and expire_time_ms > self._time_ms():
                return value
            else:
                return None
        else:
            for _, v_e in self.db.iterator(prefix=key):
                value, expire_time_ms = pickle.loads(v_e)
                if not must_be_fresh or expire_time_ms is not None and expire_time_ms > self._time_ms():
                    return value
            return None

    def _remove(self, key: bytes) -> bool:
        """
        Remove value from levelDB. Return whether removal is successful.

        :param key: bytes.
        :return: True if a data packet is being removed.
        """
        if self._get(key) is not None:
            self.db.delete(key)
            return True
        else:
            return False