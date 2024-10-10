import asyncio as aio
from hashlib import sha256
import logging
from contextlib import suppress
from ndn.encoding.tlv_var import parse_tl_num
from ndn.encoding import Name, Component, parse_data, NonStrictName
from ndn.name_tree import NameTrie
import time
from typing import Optional


class Storage:
    cache = NameTrie()

    def __init__(self):
        """
        Interface for a unified key-value storage API.
        """
        self.write_back_task = aio.create_task(self._periodic_write_back())
        self.logger = logging.getLogger(__name__)

    def __del__(self):
        self.write_back_task.cancel()

    def _put(self, key: bytes, data: bytes, expire_time_ms: int=None):
        raise NotImplementedError

    def _put_batch(self, keys: list[bytes], values: list[bytes], expire_time_mss:list[Optional[int]]):
        raise NotImplementedError

    def _get(self, key: bytes, can_be_prefix: bool=False, must_be_fresh: bool=False) -> bytes:
        raise NotImplementedError

    def _remove(self, key: bytes) -> bool:
        raise NotImplementedError


    ###### wrappers around key-value store
    async def _periodic_write_back(self):
        with suppress(aio.CancelledError):
            while True:
                self._write_back()
                await aio.sleep(10)

    @staticmethod
    def _get_name_bytes_wo_tl(name: NonStrictName) -> bytes:
        # remove name's TL as key to support efficient prefix search
        name = Name.to_bytes(name)
        offset = 0
        offset += parse_tl_num(name, offset)[1]
        offset += parse_tl_num(name, offset)[1]
        return name[offset:]
    
    @staticmethod
    def _time_ms():
        return int(time.time() * 1000)

    def _write_back(self):
        keys = []
        values = []
        expire_time_mss = []
        for name, (data, expire_time_ms) in self.cache.iteritems(prefix=[], shallow=True):
            keys.append(self._get_name_bytes_wo_tl(name))
            values.append(data)
            expire_time_mss.append(expire_time_ms)
        if len(keys) > 0:
            self._put_batch(keys, values, expire_time_mss)
            self.logger.info(f'Cache write back {len(keys)} items')
        self.cache = NameTrie()

    def put_data_packet(self, name: NonStrictName, data: bytes):
        """
        Insert a data packet named ``name`` with value ``data``.
        This method will parse ``data`` to get its freshnessPeriod, and compute its expiration time\
            by adding the freshnessPeriod to the current time.
        
        :param name: NonStrictName. The name of the data packet.
        :param data: bytes. The value of the data packet.
        """
        _, meta_info, _, _ = parse_data(data)
        expire_time_ms = self._time_ms()
        if meta_info.freshness_period:
            expire_time_ms += meta_info.freshness_period

        # write data packet and freshness_period to cache
        name = Name.normalize(name)
        self.cache[name] = (data, expire_time_ms)
        self.logger.info(f'Cache save: {Name.to_str(name)}')

    def get_data_packet(self, name: NonStrictName, can_be_prefix: bool=False,
                        must_be_fresh: bool=False) -> Optional[bytes]:
        """
        Get a data packet named ``name``.

        :param name: NonStrictName. The name of the data packet. 
        :param can_be_prefix: bool. If true, use prefix match instead of exact match.
        :param must_be_fresh: bool. If true, ignore expired data.
        :return: The value of the data packet.
        """
        # can_be_prefix must be set to False by default because _delete_single_data would not otherwise be specific enough.
        # must_be_fresh must be set to False by default because we want the delete commands to find data we want deleted, regardless of whether it is fresh or not.
        name = Name.normalize(name)
        if Component.get_type(name[-1]) == Component.TYPE_IMPLICIT_SHA256:
            data = self.get_data_packet(name[:-1], can_be_prefix, must_be_fresh)
            if sha256(data).digest() == Component.get_value(name[-1]):
                self.logger.info('Data digest matches the ImplicitSha256Digest')
                return data
            else:
                raise ValueError("Data digest does not match ImplicitSha256Digest")
        else:
            # cache lookup
            try:
                if not can_be_prefix:
                    data, expire_time_ms = self.cache[name]
                    if not must_be_fresh or expire_time_ms > self._time_ms():
                        self.logger.info('get from cache')
                        return data
                else:
                    it = self.cache.itervalues(prefix=name, shallow=True)
                    while True:
                        data, expire_time_ms = next(it)
                        if not must_be_fresh or expire_time_ms > self._time_ms():
                            self.logger.info('get from cache')
                            return data
            # not in cache, lookup in storage
            except (KeyError, StopIteration):
                key = self._get_name_bytes_wo_tl(name)
                return self._get(key, can_be_prefix, must_be_fresh)

    def remove_data_packet(self, name: NonStrictName) -> bool:
        """
        Remove a data packet named ``name``.

        :param name: NonStrictName. The name of the data packet. 
        :return: True if a data packet is being removed.
        """
        removed = False
        name = Name.normalize(name)
        try:
            del self.cache[name]
            removed = True
        except KeyError:
            pass
        if self._remove(self._get_name_bytes_wo_tl(name)):
            removed = True
        return removed
