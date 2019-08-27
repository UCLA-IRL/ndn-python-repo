# -*- coding: utf-8 -*-
"""
    NDN Repo service discovery.
    @Author jonnykong@cs.ucla.edu

    @Date   2019-08-26
"""

import asyncio
import logging
import time
from pyndn import Face, Interest, Name
from pyndn.security import KeyChain
from typing import List

ADV_PREFIX = '/sd/adv'
EXPIRE_DURATION = 10

class ServiceDiscovery(object):

    def __init__(self, repo_unique_prefix: Name, face: Face, keychain: KeyChain):
        """
        After startup, broadcast service prefixes periodically
        """
        self.repo_unique_prefix = repo_unique_prefix
        self.face = face
        self.keychain = keychain
        self.services = dict()  # Name -> int(timestamp in seconds)

        self.face.setInterestFilter(Name(ADV_PREFIX), self.on_adv)
        logging.info('Set interest filter: {}'.format(ADV_PREFIX))

        event_loop = asyncio.get_event_loop()
        event_loop.create_task(self.adv_periodically())
    
    def get_services(self) -> List[Name]:
        """
        Return a list of service names.
        """
        ret = []
        for s in self.services:
            ret.append(s)
        return ret

    def on_adv(self, _prefix, interest: Interest, face, _filter_id, _filter):
        service = interest.getName()[len(Name(ADV_PREFIX)):]
        if self.update_services(service):
            logging.info('New service discovered: {}'.format(service.toUri()))
        else:
            logging.info('Existing service refreshed: {}'.format(service.toUri()))

    def update_services(self, service: Name):
        """
        Add a new service to cache, or refresh existing services.
        Return whether a new service has been added.
        """
        time_cur = int(time.time())
        for s in self.services:
            if self.services[s] + ServiceDiscovery.EXPIRE_DURATION < time_cur:
                del self.services[s]
            elif val == service:
                self.services[service] = time_cur
                return False
        self.services[s] = time_cur
        return True

    async def adv_periodically(self):
        """
        Periodically broadcast one's prefix
        """
        while True:
            interest = Interest(Name(ADV_PREFIX).append(self.repo_unique_prefix))
            self.face.expressInterest(interest, (lambda interest, data: None), None, None)
            await asyncio.sleep(1)