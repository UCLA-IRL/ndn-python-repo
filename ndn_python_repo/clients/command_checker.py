# -----------------------------------------------------------------------------
# NDN Repo insert check tester.
#
# @Author jonnykong@cs.ucla.edu
# @Date   2019-09-23
# -----------------------------------------------------------------------------

import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import argparse
import asyncio as aio
from ..command.repo_commands import RepoCommandParameter, RepoCommandResponse
from ..utils.pubsub import PubSub
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName, Component, TlvModel, DecodeError
from ndn.types import InterestNack, InterestTimeout
import time
from typing import Optional


class CommandChecker(object):
    def __init__(self, app: NDNApp, pb: PubSub):
        """
        This client sends check interests to the repo.

        :param app: NDNApp.
        :param pb: PubSub.
        """
        self.app = app
        self.pb = pb
        self.process_id_to_response = dict()
        self.process_id_to_last_check_tp = dict()
        
        aio.ensure_future(self._schedule_unsubscribe())

    def check(self, repo_name: NonStrictName, process_id: int) -> Optional[RepoCommandResponse]:
        """
        Check the status of process ``process_id`` against repo ``repo_name``. This function\
            returns the in-memory process status, therefore it returns immediately.
        :return: Optional[RepoCommandResponse]. The last known status of ``process_id``. Therefore,\
                the first call to a process, it returns None.
        """
        # If process_id is not seen before, subscribe to its status with PubSub
        if process_id not in self.process_id_to_response:
            topic = repo_name + ['check', str(process_id)]
            cb = self.make_on_msg(process_id)
            self.pb.subscribe(topic, cb)
            self.process_id_to_response[process_id] = None
            logging.info('CommandChecker subscribing to {}'.format(Name.to_str(topic)))

        # Remember when this process is last checked
        self.process_id_to_last_check_tp[process_id] = int(time.time())
       
        return self.process_id_to_response[process_id]
        

    def make_on_msg(self, process_id: int):
        """
        Create a callback for receiving the status of process ``process_id``.
        :param process_id: int.
        """
        def on_msg(msg):
            """
            The callback updates the in-memory process status upon receiving an status update.
            """
            try:
                cmd_response = RepoCommandResponse.parse(msg)
            except DecodeError as exc:
                logging.warning('Response blob decoding failed')
                return None
            except Exception as e:
                logging.warning(e)
                return None
            self.process_id_to_response[process_id] = cmd_response
        return on_msg

    async def _schedule_unsubscribe(self, period: int=10):
        """
        Periodically unsubscribe processes that has not been checked for a while.
        """
        self._unsubscribe_inactive_processes()
        await aio.sleep(period)
        aio.ensure_future(self._schedule_unsubscribe(period))

    def _unsubscribe_inactive_processes(self):
        for process_id, last_check_tp in self.process_id_to_last_check_tp.items():
            if last_check_tp > int(time.time()) + 10:
                del self.process_id_to_response[process_id]
                del self.process_id_to_last_check_tp[process_id]
                topic = repo_name + ['check', str(process_id)]
                self.pb.unsubscribe(topic)
                logging.info('CommandChecker unsubscribed from {}'.format(Name.to_str(topic)))
