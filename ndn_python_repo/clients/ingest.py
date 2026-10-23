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
from ndn.encoding import Name, NonStrictName, Links, ContentType, Signer
from ndn.types import InterestNack, InterestTimeout, ValidationFailure, Validator
from ndn.utils import timestamp, gen_nonce_64
from ..command import ObjParam, EmbName
from typing import Optional


class _CommandSigner(Signer):
    """
    Wraps a Signer and adds SignatureTime and SignatureNonce, which the repo
    requires on ingest command Interests.
    """

    def __init__(self, signer: Signer):
        self.signer = signer

    def write_signature_info(self, signature_info):
        self.signer.write_signature_info(signature_info)
        signature_info.signature_time = timestamp()
        signature_info.signature_nonce = gen_nonce_64()

    def get_signature_value_size(self):
        return self.signer.get_signature_value_size()

    def write_signature_value(self, wire, contents):
        return self.signer.write_signature_value(wire, contents)


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
                          register_prefix: Optional[NonStrictName] = None,
                          signer: Optional[Signer] = None,
                          validator: Optional[Validator] = None) -> bool:
        """
        Ingest a single Data packet into the remote repo.

        :param data_name: NonStrictName. Name of the Data packet.
        :param content: bytes. Content of the Data packet.
        :param freshness_period: Freshness of the Data packet.
        :param forwarding_hint: NonStrictName. The forwarding hint the repo uses when fetching data.
        :param register_prefix: NonStrictName. If given, the repo starts serving reads under this\
            prefix once the data is stored.
        :param signer: Signer whose certificate is authorized by the repo's trust schema.\
            If omitted, the app keychain's default signer is used.
        :param validator: Validator for the repo's signed reply. If omitted, the app's default\
            Data validator is used.
        :return: True if the repo acknowledged the ingest command, False if every attempt\
            was NACKed by the repo or timed out.
        """
        data_name = Name.normalize(data_name)
        self.encoded_packets[Name.to_str(data_name)] = self.app.prepare_data(
            data_name, content, freshness_period=freshness_period)

        # Serve the Data packet so the repo can fetch it
        if Name.is_prefix(self.prefix, data_name):
            self.app.set_interest_filter(data_name, self._on_interest)
        else:
            await self.app.register(data_name, self._on_interest)

        cmd_param = ObjParam()
        cmd_param.name = data_name
        if forwarding_hint is not None:
            cmd_param.forwarding_hint = Links()
            cmd_param.forwarding_hint.names = [forwarding_hint]
        if register_prefix is not None:
            cmd_param.register_prefix = EmbName()
            cmd_param.register_prefix.name = register_prefix

        int_name = self.repo_name + Name.from_str('ingest')
        if signer is None:
            signer = self.app.keychain.get_signer({})
        signer = _CommandSigner(signer)
        n_retries = 3
        while n_retries > 0:
            try:
                # Each attempt is a new signed Interest: SignatureTime and SignatureNonce are
                # covered by params-sha256, so a resend never reuses a name the repo replied to.
                _, meta_info, _ = await self.app.express_interest(
                    int_name, cmd_param.encode(), can_be_prefix=False, lifetime=10000,
                    signer=signer, validator=validator)
                if meta_info is not None and meta_info.content_type == ContentType.NACK:
                    self.logger.info(f'Ingest of {Name.to_str(data_name)} rejected by repo')
                    n_retries -= 1
                    continue
                self.logger.info(f'Ingest of {Name.to_str(data_name)} acknowledged by repo')
                return True
            except InterestNack as e:
                self.logger.info(f'Nacked with reason={e.reason}')
                n_retries -= 1
                await aio.sleep(1)
            except InterestTimeout:
                self.logger.info('Timeout waiting for ingest ack')
                n_retries -= 1
            except ValidationFailure:
                self.logger.info('Reply to ingest command failed validation')
                n_retries -= 1
        return False
