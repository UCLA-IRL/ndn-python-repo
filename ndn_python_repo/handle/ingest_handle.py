# -----------------------------------------------------------------------------
# Direct ingest protocol.
#
# One Interest, one Data: the producer sends a single ingest Interest naming
# the Data to be stored; the repo fetches and stores that Data, then replies
# to the same Interest with an empty Data packet as acknowledgement, or with
# an application-level NACK if the command failed. Both replies are signed
# by the repo.
#
# The ingest Interest itself is unsigned. Its ApplicationParameters carry the
# command as a signed Data packet, named /<repo_name>/ingest/<timestamp>/<nonce>.
# The params-sha256 name component covers that Data packet, so every command
# (including a resend) has a distinct name and each reply answers exactly one
# Interest name.
#
# @Author regmisuravi@gmail.com
# @Date   2026-06-30
# -----------------------------------------------------------------------------

import asyncio as aio
import base64
import logging
import os
from pathlib import Path

from ndn.app import NDNApp, ReplyFunc, Validator, ValidResult
from ndn.app_support.light_versec import Checker, LvsModel, TypeNumber, compile_lvs, lvs_validator
from ndn.encoding import Name, NonStrictName, Component, ContentType, parse_data, tlv_parse
from ndn.security import Keychain
from ndn.security.validator.cascade_validator import MemoryKeyStorage
from ndn.utils import timestamp
from .read_handle import ReadHandle
from .utils import fetch_object
from ..command import ObjParam, RepoStatCode
from ..storage import Storage
from typing import Optional


def create_ingest_validator(app: NDNApp, security_config: Optional[dict]) -> Optional[Validator]:
    """
    Create the validator for ingest commands from the ``ingest_security`` config section.

    The signed command Data is checked against an LVS trust schema, and the signing certificate
    chain is fetched from the network and validated up to the configured trust anchor.

    :param app: NDNApp. Used to fetch certificates in the signing chain.
    :param security_config: the ``ingest_security`` config section, or None.
    :return: the validator, or None if ``ingest_security`` is not configured.
    """
    if not security_config:
        return None

    anchor_path = security_config.get('trust_anchor')
    schema_path = security_config.get('trust_schema')
    if not anchor_path or not schema_path:
        raise ValueError('ingest_security requires both trust_anchor and trust_schema')

    resolved_anchor = Path(os.path.expanduser(os.path.expandvars(anchor_path)))
    anchor_file = resolved_anchor.read_bytes()
    if anchor_file.startswith(b'\x06'):
        trust_anchor = anchor_file
    else:
        trust_anchor = base64.b64decode(b''.join(anchor_file.split()), validate=True)
    resolved_schema = Path(os.path.expanduser(os.path.expandvars(schema_path)))
    schema_file = resolved_schema.read_bytes()
    if schema_file.startswith(bytes([TypeNumber.VERSION])):
        # LVS binary format, compiled from the trust schema elsewhere
        lvs_model = LvsModel.parse(schema_file)
    else:
        lvs_model = compile_lvs(schema_file.decode())

    return lvs_validator(Checker(lvs_model, {}), app, trust_anchor, MemoryKeyStorage())


class DirectIngestHandle:
    """
    Repo-side handler for the direct ingest protocol.
    Listens on <repo_name>/ingest, and processes each command as a single Interest/Data

    1. Producer sends an unsigned Interest to <repo_name>/ingest/params-sha256=<digest>,
       with AppParam = a signed Data packet named <repo_name>/ingest/<timestamp>/<nonce>,
       whose Content is ObjParam { name, forwarding_hint, ... }.
    2. Repo validates the command Data, then fetches and stores the requested Data, as in insert.
    3. Repo replies to the original ingest Interest with an empty signed Data packet,
       or with an application-level NACK (ContentType=NACK) if the command failed.
    """

    REPLY_MARGIN_MS = 500  # reply this long before the ingest Interest expires

    def __init__(self, app: NDNApp, storage: Storage, config: dict, read_handle: ReadHandle,
                 command_validator: Optional[Validator] = None, keychain: Optional[Keychain] = None):
        self.app     = app
        self.storage = storage
        self.config  = config
        self.prefix  = None
        self.ingest_prefix = None
        self._registered_prefixes = set()
        self.m_read_handle = read_handle
        self.command_validator = command_validator
        # Replies are signed with the repo's default key, so the producer can validate them
        self.signer = None
        if command_validator is not None:
            if keychain is None:
                keychain = NDNApp.default_keychain()
            self.signer = keychain.get_signer({})

    async def listen(self, prefix: NonStrictName):
        """
        Register Interest filter on <prefix>/ingest.
        Called by WriteCommandHandle.listen().

        :param prefix: NonStrictName. The repo's name prefix.
        """
        if self.command_validator is None:
            logging.warning('Direct ingest is disabled: ingest_security is not configured')
            return

        self.prefix   = Name.normalize(prefix)
        self.ingest_prefix = self.prefix + Name.from_str('ingest')
        self.app.attach_handler(self.ingest_prefix, self._on_insert_interest, self._accept_unsigned_interest)
        await self.app.register(self.ingest_prefix)
        logging.info(f'DirectIngestHandle listening on {Name.to_str(self.ingest_prefix)}')

    @staticmethod
    async def _accept_unsigned_interest(_name, sig_ptrs, _context) -> ValidResult:
        """
        The command is authorized by the signed Data it carries, which ``_process_command``
        validates, so the ingest Interest itself must be unsigned.
        """
        if sig_ptrs.signature_info is None:
            return ValidResult.ALLOW_BYPASS
        return ValidResult.FAIL

    # Ingest Interest entry point.

    def _on_insert_interest(self, int_name, app_param, reply: ReplyFunc, context):
        """
        Parse the command Data, and start validating it only if it is well-formed.
        A command that is not a Data packet named <repo_name>/ingest/<timestamp>/<nonce>
        violates the protocol, and is dropped without a reply.
        """
        try:
            cmd_name, _, content, sig_ptrs = parse_data(app_param)
        except Exception as e:
            logging.warning(f'ingest.drop.malformed {Name.to_str(int_name)}: {e}')
            return
        if not (len(cmd_name) == len(self.ingest_prefix) + 2
                and Name.is_prefix(self.ingest_prefix, cmd_name)
                and Component.get_type(cmd_name[-2]) == Component.TYPE_TIMESTAMP):
            logging.warning(f'ingest.drop.bad_command_name {Name.to_str(cmd_name)}')
            return

        aio.create_task(self._process_command(int_name, cmd_name, content, sig_ptrs, reply, context))

    async def _process_command(self, int_name, cmd_name, content, sig_ptrs, reply: ReplyFunc, context):
        """
        Validate the command Data with ``command_validator``, then process the ObjParam it carries.
        Commands that fail validation are dropped without a reply, before fetching any Data.
        """
        if await self.command_validator(cmd_name, sig_ptrs, context) != ValidResult.PASS:
            logging.warning(f'ingest.drop.unvalidated {Name.to_str(cmd_name)}')
            return

        try:
            param = tlv_parse(ObjParam, content)
        except Exception as e:
            logging.warning(f'ingest.parse.fail: {e}')
            self._reply_nack(int_name, reply)
            return

        logging.info(f'ingest.received {Name.to_str(cmd_name)}')
        await self._process_insert(int_name, param, reply, context['deadline'])

    async def _process_insert(self, int_name, param: ObjParam, reply: ReplyFunc, deadline: int):
        """
        Fetch and store the requested Data, then reply to int_name with an empty
        Data packet as acknowledgement, or with an application-level NACK
        (ContentType=NACK) on failure.

        :param deadline: the ingest Interest's expiry, as a timestamp in milliseconds.
        """
        # Fetch, bounded by the ingest Interest's deadline so that the reply
        # (ack or NACK) still reaches the producer before its PIT entry expires.
        deadline_s = max(deadline - timestamp() - self.REPLY_MARGIN_MS, 0) / 1000.0
        try:
            status_code, insert_num = await aio.wait_for(
                fetch_object(self.app, self.storage, param), timeout=deadline_s)
        except aio.TimeoutError:
            logging.error(f'ingest.fetch.deadline {Name.to_str(int_name)} deadline={deadline_s}s')
            self._reply_nack(int_name, reply)
            return

        if status_code == RepoStatCode.MALFORMED:
            logging.warning(f'ingest.malformed {Name.to_str(int_name)}')
            self._reply_nack(int_name, reply)
            return
        data_name = Name.to_str(param.name)
        if status_code != RepoStatCode.COMPLETED:
            logging.error(f'ingest.fetch.fail {data_name} inserted={insert_num}')
            self._reply_nack(int_name, reply)
            return

        logging.info(f'ingest.data.saved {data_name} count={insert_num}')

        register_prefix = param.register_prefix.name if param.register_prefix else None
        if register_prefix:
            prefix_str = Name.to_str(register_prefix)
            if prefix_str not in self._registered_prefixes:
                self._registered_prefixes.add(prefix_str)
                self.m_read_handle.listen(register_prefix)
                logging.info(f'ingest.prefix.registered {prefix_str}')

        # Ack
        reply(self.app.make_data(int_name, None, self.signer))
        logging.info(f'ingest.ack.sent data={data_name}')

    def _reply_nack(self, int_name, reply: ReplyFunc):
        """
        Reply to the ingest Interest with an application-level NACK, so the
        producer learns about the failure without waiting for its Interest to time out.
        """
        reply(self.app.make_data(int_name, None, self.signer, content_type=ContentType.NACK))
        logging.info(f'ingest.nack.sent {Name.to_str(int_name)}')
