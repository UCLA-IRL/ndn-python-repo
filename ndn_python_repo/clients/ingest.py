# -----------------------------------------------------------------------------
# NDN Repo ingest client.
#
# @Author regmisuravi@gmail.com
# @Date   2026-06-30
# -----------------------------------------------------------------------------

import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName, Links
from ndn.types import InterestNack, InterestTimeout
from ..command import IngestCmdParam, EmbName
from typing import Optional


class IngestClient(object):
    """
    A client to ingest a single Data packet into the repo using the direct
    ingest protocol. Unlike ``PutfileClient``, this does not shard content
    into segments or use Pub-Sub: the client serves one Data packet directly,
    and the ingest command completes as soon as the repo acknowledges with a
    Data reply.
    """

    def __init__(self, app: NDNApp, prefix: NonStrictName, repo_name: NonStrictName):
        """
        :param app: NDNApp.
        :param prefix: NonStrictName. The name of this client.
        :param repo_name: NonStrictName. Routable name to remote repo.
        """
        self.app = app
        self.prefix = prefix
        self.repo_name = Name.normalize(repo_name)
        self.encoded_packets = {}
        self.logger = logging.getLogger(__name__)

    def _on_interest(self, int_name, _int_param, _app_param):
        name_str = Name.to_str(int_name)
        if name_str in self.encoded_packets:
            self.app.put_raw_packet(self.encoded_packets[name_str])
            self.logger.info(f'Serve data: {name_str}')
        else:
            self.logger.info(f'Data does not exist: {name_str}')

    async def ingest_data(self, data_name: NonStrictName, content: bytes, freshness_period: int = 0,
                          forwarding_hint: Optional[NonStrictName] = None,
                          register_prefix: Optional[NonStrictName] = None) -> bool:
        """
        Ingest a single Data packet into the remote repo.

        :param data_name: NonStrictName. Name of the Data packet.
        :param content: bytes. Content of the Data packet.
        :param freshness_period: Freshness of the Data packet.
        :param forwarding_hint: NonStrictName. The forwarding hint the repo uses when fetching data.
        :param register_prefix: NonStrictName. If given, the repo starts serving reads under this\
            prefix once the data is stored.
        :return: True if the repo acknowledged the ingest command.
        """
        data_name = Name.normalize(data_name)
        self.encoded_packets[Name.to_str(data_name)] = self.app.prepare_data(
            data_name, content, freshness_period=freshness_period)

        # Serve the Data packet so the repo can fetch it
        if Name.is_prefix(self.prefix, data_name):
            self.app.set_interest_filter(data_name, self._on_interest)
        else:
            await self.app.register(data_name, self._on_interest)

        cmd_param = IngestCmdParam()
        cmd_param.data_name = data_name
        if forwarding_hint is not None:
            cmd_param.forwarding_hint = Links()
            cmd_param.forwarding_hint.names = [forwarding_hint]
        if register_prefix is not None:
            cmd_param.register_prefix = EmbName()
            cmd_param.register_prefix.name = register_prefix

        int_name = self.repo_name + Name.from_str('ingest')
        n_retries = 3
        while n_retries > 0:
            try:
                await self.app.express_interest(
                    int_name, cmd_param.encode(), must_be_fresh=False, can_be_prefix=False, lifetime=10000)
                self.logger.info(f'Ingest of {Name.to_str(data_name)} acknowledged by repo')
                return True
            except InterestNack as e:
                self.logger.info(f'Nacked with reason={e.reason}')
                n_retries -= 1
                await aio.sleep(1)
            except InterestTimeout:
                self.logger.info('Timeout waiting for ingest ack')
                n_retries -= 1
        return False
