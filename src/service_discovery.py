# -*- coding: utf-8 -*-
"""
    NDN Repo service discovery.
    @Author jonnykong@cs.ucla.edu

    @Date   2019-08-26
"""

import asyncio
import logging
import time
from asyncndn import fetch_data_packet
from pyndn import Face, Interest, Name
from pyndn.security import KeyChain
from typing import List

ADV_PREFIX = '/repo/sd/adv'
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

        self.face.registerPrefix(Name(ADV_PREFIX), None,
                                 lambda prefix: logging.error('Prefix registration failed: %s', prefix))
        self.face.setInterestFilter(Name(ADV_PREFIX), self.on_adv)
        logging.info('Set interest filter: {}'.format(ADV_PREFIX))

        event_loop = asyncio.get_event_loop()
        event_loop.create_task(self.adv_periodically())
    
    def get_services(self) -> List[Name]:
        """
        Return a list of service names.
        Due to lazy removal of expired services, need to explicitly remove services again here.
        """
        self.remove_expired()
        return [s for s in self.services]

    def on_adv(self, _prefix, interest: Interest, face, _filter_id, _filter):
        """
        Lazily remove expired services.
        """
        service = interest.getName()[len(Name(ADV_PREFIX)):]
        if service == self.repo_unique_prefix:
            logging.warning('Received sd adv with same name: {}'.format(service.toUri()))
            return
        if self.update_services(service):
            logging.info('New service discovered: {}'.format(service.toUri()))
        else:
            logging.info('Existing service refreshed: {}'.format(service.toUri()))
    
    def remove_expired(self):
        """
        Remove expired services from cache.
        """
        time_now = int(time.time())
        for s in list(self.services):
            if self.services[s] + EXPIRE_DURATION < time_now:
                del self.services[s]
                logging.info('Removed service from list: {}'.format(s.toUri()))

    def update_services(self, service: Name):
        """
        Add a new service to cache, or refresh existing services.
        Return whether a new service has been added.
        """
        self.remove_expired()
        time_now = int(time.time())
        for s in self.services:
            if s == service:
                self.services[service] = time_now
                return False
        self.services[service] = time_now
        return True

    async def adv_periodically(self):
        """
        Periodically broadcast one's prefix
        """
        while True:
            self.remove_expired()   # Not necessary here
            interest = Interest(Name(ADV_PREFIX).append(self.repo_unique_prefix))
            interest.setInterestLifetimeMilliseconds(1000)
            self.face.expressInterest(interest, (lambda interest, data: None), None, None)
            await asyncio.sleep(1)