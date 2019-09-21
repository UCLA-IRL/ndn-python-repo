import asyncio
import os
import sys
import logging
import asyncio
import pickle
from typing import Optional, Callable, Union
from pyndn import Blob, Face, Name, Data, Interest, NetworkNack
from pyndn.security import KeyChain
from pyndn.encoding import ProtobufTlv
from storage import Storage


class ReadHandle(object):
    def __init__(self, face: Face, keychain: KeyChain, storage: Storage):
        self.face = face
        self.keychain = keychain
        self.storage = storage

    def listen(self, name: Name):
        """
        This function needs to be called for prefix of all data stored.
        """
        self.face.registerPrefix(name, None,
                                 lambda prefix: logging.error('Prefix registration failed: %s', prefix))
        self.face.setInterestFilter(name, self.on_interest)
        logging.info('Read handle: listening to {}'.format(str(name)))

    def on_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        name = interest.getName()

        if not self.storage.exists(str(name)):
            return

        raw_data = self.storage.get(str(name))
        data = Data()
        data.wireDecode(Blob(pickle.loads(raw_data)))
        self.face.putData(data)

        logging.info('Read handle: serve data {}'.format(interest.getName()))