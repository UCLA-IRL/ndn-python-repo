from ndn.encoding.tlv_var import parse_tl_num
from ndn.encoding import Name, parse_data, NonStrictName
import time


class Storage:
    """
    Interface for storage functionalities
    """
    def _put(self, key: bytes, data: bytes, expire_time_ms: int=None):
        raise NotImplementedError

    def _get(self, key: bytes, can_be_prefix=False, must_be_fresh=False) -> bytes:
        raise NotImplementedError

    def _remove(self, key: bytes) -> bool:
        raise NotImplementedError

    def put_data_packet(self, name: NonStrictName, data: bytes):
        # remove name's TL as key to support prefix search
        name = Name.to_bytes(name)
        offset = 0
        offset += parse_tl_num(name, offset)[1]
        offset += parse_tl_num(name, offset)[1]
        key = name[offset:]
        
        # compute expire_time_ms by adding freshnessPeriod to current time
        _, meta_info, _, _ = parse_data(data)
        expire_time_ms = int(time.time() * 1000)
        if meta_info.freshness_period:
            expire_time_ms += meta_info.freshness_period

        self._put(key, data, expire_time_ms)
    
    def get_data_packet(self, name: NonStrictName, can_be_prefix=False, must_be_fresh=False):
        # remove name TL
        name = Name.to_bytes(name)
        offset = 0
        offset += parse_tl_num(name, offset)[1]
        offset += parse_tl_num(name, offset)[1]
        key = name[offset:]

        return self._get(key, can_be_prefix, must_be_fresh)
    
    def remove_data_packet(self, name: NonStrictName):
        name = Name.to_bytes(name)
        offset = 0
        offset += parse_tl_num(name, offset)[1]
        offset += parse_tl_num(name, offset)[1]
        key = name[offset:]

        return self._remove(key)