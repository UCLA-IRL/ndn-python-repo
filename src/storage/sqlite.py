import os
import sqlite3
from typing import List, Optional
from .storage_base import Storage


class SqliteStorage(Storage):
    def __init__(self, db_path: str = 'repo.db'):
        """
        Init table "data" with the attribute "key" being the primary key
        :param db_path: str. Path to database file
        """
        self.conn = sqlite3.connect(os.path.expanduser(db_path))
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS data (
                key     TEXT PRIMARY KEY,
                value   BLOB
            )
        """)
        self.conn.commit()

    def __del__(self):
        self.conn.close()

    def put(self, key: str, value: bytes):
        """
        Insert document into sqlite3, overwrite if already exists.
        :param key: str
        :param value: bytes
        """
        c = self.conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO data (key, value) VALUES (?, ?)
        """, (key, value))
        self.conn.commit()

    def get(self, key: str) -> Optional[bytes]:
        """
        Get value from sqlite3.
        :param key: str
        :return: bytes
        """
        c = self.conn.cursor()
        c.execute("""
            SELECT  value
            FROM    data
            WHERE   key = ?
        """, (key, ))
        ret = c.fetchone()
        return ret[0] if ret else None

    def exists(self, key: str) -> bool:
        """
        Return whether document exists.
        :param key: str
        :return: bool
        """
        return self.get(key) is not None

    def remove(self, key: str) -> bool:
        """
        Return whether removal is successful
        :param key: str
        :return: bool
        """
        c = self.conn.cursor()
        n_removed = c.execute("""
            DELETE FROM data
            WHERE key = ?
        """, (key, )).rowcount
        return n_removed > 0

    def keys(self) -> List[str]:
        """
        Get the list of keys
        :return: List[str]
        """
        ret = []
        c = self.conn.cursor()
        c.execute("""
            SELECT  key
            FROM    data
        """)
        for row in c:
            ret.append(row[0])
        return ret