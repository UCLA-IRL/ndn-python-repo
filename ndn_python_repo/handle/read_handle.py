import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name
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
        self.logger = logging.getLogger(__name__)
        if self.register_root:
            self.listen(Name.from_str('/'))

    def listen(self, prefix):
        """
        This function needs to be called for prefix of all data stored.
        :param prefix: NonStrictName.
        """
        self.app.route(prefix)(self._on_interest)
        self.logger.info(f'Read handle: listening to {Name.to_str(prefix)}')
    
    def unlisten(self, prefix):
        """
        :param prefix: NonStrictName.
        """
        aio.ensure_future(self.app.unregister(prefix))
        self.logger.info(f'Read handle: stop listening to {Name.to_str(prefix)}')

    def _on_interest(self, int_name, int_param, _app_param):
        """
        Repo responds to Interests with mustBeFresh flag, following the same logic as the Content Store in NFD
        """
        logging.debug(f'Repo got Interest with{"out" if not int_param.must_be_fresh else ""} '
                      f'MustBeFresh flag set for name {Name.to_str(int_name)}')
        data_bytes = self.storage.get_data_packet(int_name, int_param.can_be_prefix, int_param.must_be_fresh)
        if data_bytes is None:
            return
        self.app.put_raw_packet(data_bytes)
        self.logger.info(f'Read handle: serve data {Name.to_str(int_name)}')
