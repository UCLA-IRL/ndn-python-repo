import logging
import pickle
from ndn.app import NDNApp
from ndn.encoding import Name, Component, MetaInfo
from src.storage import Storage
from datetime import datetime


class ReadHandle(object):
    """
    ReadCommandHandle processes ordinary interests, and return corresponding data if available.
    """
    def __init__(self, app: NDNApp, storage: Storage):
        """
        :param app: NDNApp.
        :param storage: Storage.
        """
        self.app = app
        self.storage = storage

    def listen(self, name):
        """
        This function needs to be called for prefix of all data stored.
        :param name: NonStrictName.
        """
        self.app.route(name)(self._on_interest)
        logging.info(f'Read handle: listening to {Name.to_str(name)}')

    def _on_interest(self, int_name, _int_param, _app_param):
        logging.info(datetime.now().strftime("1： %H:%M:%S.%f "))
        if not self.storage.exists(Name.to_str(int_name)):
            return
        (_, meta_info, content) = pickle.loads(self.storage.get(Name.to_str(int_name)))
        meta_info = MetaInfo.parse(meta_info)
        self.app.put_data(int_name, content, meta_info=meta_info)
        logging.info(datetime.now().strftime("2： %H:%M:%S.%f "))
        logging.info(f'Read handle: serve data {Name.to_str(int_name)}')