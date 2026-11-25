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
from ndn.app import NDNApp, Validator
from ndn.encoding import Name, NonStrictName, Component, Links, ContentType, MetaInfo, Signer, make_data, tlv_encode
from ndn.security import Keychain
from ndn.security.validator import sha256_digest_checker
from ndn.types import InterestNack, InterestTimeout, ValidationFailure
from ndn.utils import timestamp, gen_nonce_64
from ..command import ObjParam, EmbName
from typing import Optional


def make_ingest_command(repo_name: NonStrictName, cmd_param: ObjParam, signer: Signer) -> bytes:
    """
    Make the signed Data packet that carries an ingest command, named
    <repo_name>/ingest/<timestamp>/<nonce> so that every command is distinct.

    :param repo_name: NonStrictName. Routable name to remote repo.
    :param cmd_param: ObjParam. The command.
    :param signer: Signer whose certificate is authorized by the repo's trust schema.
    :return: the encoded command Data packet.
    """
    cmd_name = Name.normalize(repo_name) + Name.from_str('ingest') + [
        Component.from_timestamp(timestamp() * 1000), Component.from_number(gen_nonce_64(), Component.TYPE_GENERIC)]
    return bytes(make_data(cmd_name, MetaInfo(), tlv_encode(cmd_param), signer=signer))


class IngestClient(object):
    """
    A client to ingest a single Data packet into the repo using the direct
    ingest protocol. Unlike ``PutfileClient``, this does not shard content
    into segments or use Pub-Sub: the client serves one Data packet directly,
    and the ingest command completes as soon as the repo acknowledges with a
    Data reply.
    """

    def __init__(self, app: NDNApp, prefix: NonStrictName, repo_name: NonStrictName,
                 keychain: Optional[Keychain] = None):
        """
        :param app: NDNApp.
        :param prefix: NonStrictName. The name of this client.
        :param repo_name: NonStrictName. Routable name to remote repo.
        :param keychain: Keychain. Signs the served Data packet, and the ingest command when no\
            signer is given. If omitted, the default keychain is loaded when first needed.
        """
        self.app = app
        self.keychain = keychain
        self.prefix = prefix
        self.repo_name = Name.normalize(repo_name)
        self.encoded_packets = {}
        self.logger = logging.getLogger(__name__)

    def _get_keychain(self) -> Keychain:
        if self.keychain is None:
            self.keychain = NDNApp.default_keychain()
        return self.keychain

    def _on_interest(self, int_name, _app_param, reply, _context):
        name_str = Name.to_str(int_name)
        if name_str in self.encoded_packets:
            reply(self.encoded_packets[name_str])
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
            If omitted, the keychain's default signer is used.
        :param validator: Validator for the repo's signed reply. If omitted, only a\
            DigestSha256 signature is checked.
        :return: True if the repo acknowledged the ingest command, False if every attempt\
            was NACKed by the repo or timed out.
        """
        data_name = Name.normalize(data_name)
        self.encoded_packets[Name.to_str(data_name)] = self.app.make_data(
            data_name, content, self._get_keychain().get_signer({}), freshness_period=freshness_period)

        # Serve the Data packet so the repo can fetch it
        self.app.attach_handler(data_name, self._on_interest, sha256_digest_checker)
        if not Name.is_prefix(self.prefix, data_name):
            await self.app.register(data_name)

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
            signer = self._get_keychain().get_signer({})
        if validator is None:
            validator = sha256_digest_checker
        n_retries = 3
        while n_retries > 0:
            try:
                # Each attempt carries a new command Data, whose timestamp and nonce are covered
                # by params-sha256, so a resend never reuses a name the repo replied to.
                # The command Data is signed; the Interest carrying it is not.
                _, _, context = await self.app.express(
                    int_name, validator, make_ingest_command(self.repo_name, cmd_param, signer),
                    signer=None, can_be_prefix=False, lifetime=10000)
                meta_info = context['meta_info']
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
