import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, tlv_var, ndn_format_0_3
from ..storage import Storage


class ReadHandle(object):
    """
    ReadCommandHandle processes ordinary interests, and return corresponding data if exists.
    """
    def __init__(self, app: NDNApp, storage: Storage):
        """
        :param app: NDNApp.
        :param storage: Storage.
        """
        self.app = app
        self.storage = storage

    def listen(self, prefix):
        """
        This function needs to be called for prefix of all data stored.
        :param prefix: NonStrictName.
        """
        self.app.route(prefix)(self._on_interest)
        logging.info(f'Read handle: listening to {Name.to_str(prefix)}')
    
    def unlisten(self, prefix):
        """
        :param name: NonStrictName.
        """
        aio.ensure_future(self.app.unregister(prefix))
        logging.info(f'Read handle: stop listening to {Name.to_str(prefix)}')

    def _on_interest(self, int_name, _int_param, _app_param):
        if not self.storage.exists(Name.to_str(int_name)):
            return
        data_bytes = self.storage.get(Name.to_str(int_name))

        # Append TL
        type_len = tlv_var.get_tl_num_size(ndn_format_0_3.TypeNumber.DATA)
        len_len = tlv_var.get_tl_num_size(len(data_bytes))
        wire = bytearray(type_len + len_len + len(data_bytes))

        offset = 0
        offset += tlv_var.write_tl_num(ndn_format_0_3.TypeNumber.DATA, wire, offset)
        offset += tlv_var.write_tl_num(len(data_bytes), wire, offset)
        wire[offset:] = data_bytes

        self.app.put_raw_packet(wire)
        logging.info(f'Read handle: serve data {Name.to_str(int_name)}')
