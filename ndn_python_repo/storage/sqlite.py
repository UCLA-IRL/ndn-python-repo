import os
import sqlite3
from typing import List, Optional
from .storage_base import Storage


class SqliteStorage(Storage):

    def __init__(self, db_path: str):
        """
        Init table "data" with the attribute ``key`` being the primary key.

        :param db_path: str. Path to database file.
        """
        super().__init__()
        db_path = os.path.expanduser(db_path)
        if len(os.path.dirname(db_path)) > 0 and not os.path.exists(os.path.dirname(db_path)):
            try:
                os.makedirs(os.path.dirname(db_path))
            except PermissionError:
                raise PermissionError(f'Could not create database directory: {db_path}') from None

        self.conn = sqlite3.connect(os.path.expanduser(db_path))
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS data (
                key BLOB PRIMARY KEY,
                value BLOB,
                expire_time_ms INTEGER
            )
        """)
        self.conn.commit()

    def _put(self, key: bytes, value: bytes, expire_time_ms=None):
        """
        Insert value and its expiration time into sqlite3, overwrite if already exists.

        :param key: bytes.
        :param value: bytes.
        :param expire_time_ms: Optional[int]. This data is marked unfresh after ``expire_time_ms``\
            milliseconds.
        """
        c = self.conn.cursor()
        c.execute('INSERT OR REPLACE INTO data (key, value, expire_time_ms) VALUES (?, ?, ?)',
            (key, value, expire_time_ms))
        self.conn.commit()

    def _put_batch(self, keys: List[bytes], values: List[bytes], expire_time_mss:List[Optional[int]]):
        """
        Batch insert.

        :param key: List[bytes].
        :param value: List[bytes].
        :param expire_time_ms: List[Optional[int]]. The expiration time for each data in ``value``.
        """
        c = self.conn.cursor()
        c.executemany('INSERT OR REPLACE INTO data (key, value, expire_time_ms) VALUES (?, ?, ?)',
            zip(keys, values, expire_time_mss))
        self.conn.commit()

    def _get(self, key: bytes, can_be_prefix=False, must_be_fresh=False) -> Optional[bytes]:
        """
        Get value from sqlite3.

        :param key: bytes.
        :param can_be_prefix: bool. If true, use prefix match instead of exact match.
        :param must_be_fresh: bool. If true, ignore expired data.
        :return: The value of the data packet.
        """
        c = self.conn.cursor()
        query = 'SELECT value FROM data WHERE '
        if must_be_fresh:
            query += f'(expire_time_ms > {time_ms()}) AND '
        if can_be_prefix:
            query += 'hex(key) LIKE ?'
            c.execute(query, (key.hex() + '%', ))
        else:
            query += 'key = ?'
            c.execute(query, (key, ))
        ret = c.fetchone()
        return ret[0] if ret else None

    def _remove(self, key: bytes) -> bool:
        """
        Remove value from sqlite. Return whether removal is successful.

        :param key: bytes.
        :return: True if a data packet is being removed.
        """
        c = self.conn.cursor()
        n_removed = c.execute('DELETE FROM data WHERE key = ?', (key, )).rowcount
        self.conn.commit()
        return n_removed > 0