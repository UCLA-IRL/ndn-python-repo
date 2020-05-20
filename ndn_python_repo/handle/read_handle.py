import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, tlv_var
from ..storage import Storage


class ReadHandle(object):
    """
    ReadCommandHandle processes ordinary interests, and return corresponding data if exists.
    """
    def __init__(self, app: NDNApp, storage: Storage, config: dict):
        """
        :param app: NDNApp.
        :param storage: Storage.
        TODO: determine which prefix to listen on.
        """
        self.app = app
        self.storage = storage
        self.register_root = config['repo_config']['register_root']
        if self.register_root:
            self.listen(Name.from_str('/'))

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

    def _on_interest(self, int_name, int_param, _app_param):
        """
        Repo should not respond to any interest with MustBeFresh flag set.
        """
        if int_param.must_be_fresh:
            return
        data_bytes = self.storage.get_data_packet(int_name, int_param.can_be_prefix)
        if data_bytes == None:
            return
        self.app.put_raw_packet(data_bytes)
        logging.info(f'Read handle: serve data {Name.to_str(int_name)}')