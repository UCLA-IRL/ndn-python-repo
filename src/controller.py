# -*- coding: utf-8 -*-
"""
    NDN-Repo controller.
    The controller helps verifying commands for repo. Also, the controller assigns a sequence
    number to each command to guarantee consistency.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-08-21
"""

import asyncio
import json
import logging
from pyndn.security import KeyChain
from pyndn import Face, Interest, NetworkNack, Data, Name


class Controller(object):

    def __init__(self, face: Face, keychain: KeyChain, prefix: Name):
        self.face = face
        self.keychain = keychain
        self.prefix = prefix

        self.face.registerPrefix(self.prefix, None,
                                 lambda prefix: logging.error("Prefix registration failed: %s", prefix))
        self.face.setInterestFilter(Name(self.prefix).append('verify'), self.on_verify_interest)
        self.cmd_seq = 1

    def on_verify_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        if self.do_verify(interest) is False:
            logging.warning('Command verification failed: {}'.format(interest.getName()))
            return

        logging.info('Command verification success: {}'.format(interest.getName()))

        content = {'valid': True, 'seq': self.cmd_seq}
        content = json.dumps(content).encode()
        self.cmd_seq += 1

        data = Data(interest.getName())
        data.setContent(content)
        data.metaInfo.freshnessPeriod = 1000
        self.keychain.sign(data)
        self.face.putData(data)

    def do_verify(self, interest: Interest) -> bool:
        # TODO
        return True


if __name__ == "__main__":

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    face = Face()
    running = True
    keychain = KeyChain()
    face.setCommandSigningInfo(keychain, keychain.getDefaultCertificateName())
    prefix = Name('/controller')

    c = Controller(face, keychain, prefix)

    async def face_loop():
        while running:
            face.processEvents()
            await asyncio.sleep(0.001)

    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(face_loop())
    finally:
        event_loop.close()
