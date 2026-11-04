import asyncio as aio
import base64
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from Cryptodome.PublicKey import ECC
from ndn.app_support.light_versec import compile_lvs
from ndn.app_support.security_v2 import self_sign, derive_cert
from ndn.encoding import Name, Component, ContentType, InterestParam, MetaInfo, make_data, make_interest, \
    parse_interest, parse_data, tlv_encode, tlv_parse
from ndn.security import Sha256WithEcdsaSigner, DigestSha256Signer
from ndn.types import ValidationFailure, InterestTimeout, ValidResult
from ndn.utils import timestamp
from ndn_python_repo.clients.ingest import make_ingest_command
from ndn_python_repo.command import ObjParam
from ndn_python_repo.handle.ingest_handle import DirectIngestHandle, create_ingest_validator


SCHEMA = '''
#KEY: "KEY"/_/_/_
#root: "test-root"/#KEY
#producer_a: "producer-a"/#KEY <= #root
#producer_b: "producer-b"/#KEY <= #root
#ingest: "repo"/"ingest"/_/_ <= #producer_a | #producer_b
'''


def make_key(key_name):
    key = ECC.generate(curve='P-256')
    return (Name.from_str(key_name) + [Component.from_bytes(b'k')],
            key.public_key().export_key(format='DER'), key.export_key(format='DER'))


@pytest.fixture
def pki(tmp_path):
    root_key, root_pub, root_priv = make_key('/test-root/KEY')
    root_cert_name, root_cert = self_sign(root_key, root_pub, Sha256WithEcdsaSigner(root_key, root_priv))
    producer_signers = []
    certs = {}
    for producer_name in ('/producer-a/KEY', '/producer-b/KEY', '/producer-c/KEY'):
        prod_key, prod_pub, prod_priv = make_key(producer_name)
        prod_cert_name, prod_cert = derive_cert(
            prod_key, 'root', prod_pub, Sha256WithEcdsaSigner(root_cert_name, root_priv),
            datetime.now(timezone.utc), 3600)
        producer_signers.append(Sha256WithEcdsaSigner(prod_cert_name, prod_priv))
        certs[Name.to_bytes(prod_cert_name)] = bytes(prod_cert)

    anchor_path = tmp_path / 'anchor.ndncert'
    anchor_path.write_bytes(base64.b64encode(bytes(root_cert)))
    schema_path = tmp_path / 'ingest.lvs'
    schema_path.write_text(SCHEMA)

    async def express(name, validator, **_kwargs):
        # Serve certificates like the network would, validating each with the given validator
        wire = certs.get(Name.to_bytes(name))
        if wire is None:
            raise InterestTimeout()
        data_name, meta_info, content, sig_ptrs = parse_data(wire)
        context = {'meta_info': meta_info, 'sig_ptrs': sig_ptrs, 'raw_packet': wire}
        result = await validator(data_name, sig_ptrs, context)
        if result not in (ValidResult.PASS, ValidResult.ALLOW_BYPASS):
            raise ValidationFailure(data_name, meta_info, content, sig_ptrs, result)
        return data_name, content, context

    app = Mock()
    app.express = AsyncMock(side_effect=express)
    config = {'trust_anchor': str(anchor_path), 'trust_schema': str(schema_path)}
    return app, config, *producer_signers


def command(repo_name, signer):
    """Make an ingest command Data, and return its wire, name, content and signature."""
    cmd_param = ObjParam()
    cmd_param.name = Name.from_str('/data')
    wire = make_ingest_command(repo_name, cmd_param, signer)
    cmd_name, _, content, sig_ptrs = parse_data(wire)
    return wire, cmd_name, content, sig_ptrs


def validate(validator, repo_name, signer):
    _, cmd_name, _, sig_ptrs = command(repo_name, signer)
    return aio.run(validator(cmd_name, sig_ptrs, {})) == ValidResult.PASS


def listening_handle(app=None, validator=None, keychain=None):
    """Make a DirectIngestHandle listening on /repo."""
    app = app or Mock()
    app.register = AsyncMock()
    handle = DirectIngestHandle(app, Mock(), {}, Mock(), command_validator=validator or Mock(),
                                keychain=keychain or Mock())
    aio.run(handle.listen(Name.from_str('/repo')))
    return handle


def test_ingest_is_disabled_without_security_config():
    assert create_ingest_validator(Mock(), None) is None


def test_ingest_security_requires_anchor_and_schema(pki):
    _, config, _, _, _ = pki
    with pytest.raises(ValueError, match='trust_anchor and trust_schema'):
        create_ingest_validator(Mock(), {'trust_schema': config['trust_schema']})


def test_ingest_security_expands_user_home_in_paths(pki, tmp_path, monkeypatch):
    app, config, _, _, _ = pki
    home_dir = tmp_path / 'home'
    home_dir.mkdir()
    anchor_path = home_dir / 'anchor.ndncert'
    schema_path = home_dir / 'ingest.lvs'
    anchor_path.write_bytes(Path(config['trust_anchor']).read_bytes())
    schema_path.write_text(Path(config['trust_schema']).read_text())

    monkeypatch.setenv('HOME', str(home_dir))
    validator = create_ingest_validator(app, {
        'trust_anchor': '~/anchor.ndncert',
        'trust_schema': '~/ingest.lvs',
    })
    assert validator is not None


def test_ingest_security_rejects_anchor_not_matching_schema(pki, tmp_path):
    app, config, _, _, _ = pki
    schema_path = tmp_path / 'other.lvs'
    schema_path.write_text(SCHEMA.replace('"test-root"', '"other-root"'))
    with pytest.raises(ValueError, match='Trust anchor'):
        create_ingest_validator(app, {**config, 'trust_schema': str(schema_path)})


def test_ingest_command_is_named_with_timestamp_and_nonce(pki):
    _, _, producer_signer, _, _ = pki
    _, cmd_name, content, sig_ptrs = command('/repo', producer_signer)
    assert Name.is_prefix(Name.from_str('/repo/ingest'), cmd_name)
    assert len(cmd_name) == 4
    assert Component.get_type(cmd_name[2]) == Component.TYPE_TIMESTAMP
    assert tlv_parse(ObjParam, content).name == Name.from_str('/data')
    assert sig_ptrs.signature_info.key_locator.name == producer_signer.key_locator_name

    # A resend of the same command is a different command Data
    assert command('/repo', producer_signer)[1] != cmd_name


def test_ingest_validator_fetches_chain_and_accepts_authorized_producer(pki):
    app, config, producer_a_signer, producer_b_signer, _ = pki
    validator = create_ingest_validator(app, config)

    for signer in (producer_a_signer, producer_b_signer):
        assert validate(validator, '/repo', signer)
    assert app.express.await_count == 2


def test_ingest_security_accepts_lvs_binary_schema(pki, tmp_path):
    app, config, producer_signer, _, _ = pki
    schema_path = tmp_path / 'ingest.lvsb'
    schema_path.write_bytes(compile_lvs(SCHEMA).encode())
    validator = create_ingest_validator(app, {**config, 'trust_schema': str(schema_path)})

    assert validate(validator, '/repo', producer_signer)
    assert not validate(validator, '/other-repo', producer_signer)


def test_ingest_validator_rejects_name_outside_schema(pki):
    app, config, producer_signer, _, _ = pki
    validator = create_ingest_validator(app, config)

    assert not validate(validator, '/other-repo', producer_signer)


def test_ingest_validator_rejects_untrusted_signer(pki):
    app, config, _, _, unauthorized_producer = pki
    validator = create_ingest_validator(app, config)

    # This producer has a valid chain to the configured anchor, but its name is
    # not authorized by the LVS schema.
    assert not validate(validator, '/repo', unauthorized_producer)

    # Self-signed key with a producer-like name, not certified by the trust anchor
    key_name, _, priv = make_key('/producer-a/KEY')
    attacker = Sha256WithEcdsaSigner(key_name + [Component.from_str('self'), Component.from_version(1)], priv)
    assert not validate(validator, '/repo', attacker)

    # Digest signature has no KeyLocator
    assert not validate(validator, '/repo', DigestSha256Signer())


def test_ingest_drops_protocol_violations_without_reply(pki, monkeypatch):
    _, _, producer_signer, _, _ = pki
    handle = listening_handle()
    create_task = Mock()
    monkeypatch.setattr(aio, 'create_task', create_task)
    reply = Mock()
    int_name = Name.from_str('/repo/ingest')

    cmd_param = ObjParam()
    cmd_param.name = Name.from_str('/data')
    for app_param in (
            None,
            # a bare ObjParam, as in a signed-Interest command
            tlv_encode(cmd_param),
            # command Data for another repo
            command('/other-repo', producer_signer)[0],
            # command Data without the timestamp and nonce components
            make_data(Name.from_str('/repo/ingest'), MetaInfo(), tlv_encode(cmd_param), signer=producer_signer),
            make_data(Name.from_str('/repo/ingest/a/b'), MetaInfo(), tlv_encode(cmd_param), signer=producer_signer)):
        handle._on_insert_interest(int_name, app_param, reply, {})
    reply.assert_not_called()
    create_task.assert_not_called()

    # A well-formed command Data is validated in a task
    handle._on_insert_interest(int_name, command('/repo', producer_signer)[0], reply, {})
    create_task.assert_called_once()
    create_task.call_args.args[0].close()
    reply.assert_not_called()


def test_ingest_drops_unvalidated_command_without_reply(pki):
    _, _, producer_signer, _, _ = pki
    validator = AsyncMock(return_value=ValidResult.FAIL)
    app = Mock()
    handle = listening_handle(app, validator)
    reply = Mock()

    _, cmd_name, content, sig_ptrs = command('/repo', producer_signer)
    context = {'deadline': timestamp() + 10000}
    aio.run(handle._process_command(Name.from_str('/repo/ingest'), cmd_name, content, sig_ptrs, reply, context))
    validator.assert_awaited_once_with(cmd_name, sig_ptrs, context)
    reply.assert_not_called()
    app.express.assert_not_called()


def test_ingest_nacks_validated_command_with_malformed_param(pki):
    _, _, producer_signer, _, _ = pki
    app = Mock()
    handle = listening_handle(app, AsyncMock(return_value=ValidResult.PASS))
    reply = Mock()

    int_name = Name.from_str('/repo/ingest')
    cmd_name = Name.from_str('/repo/ingest') + [Component.from_timestamp(1), Component.from_str('n')]
    _, _, _, sig_ptrs = parse_data(make_data(cmd_name, MetaInfo(), b'\xff\xff', signer=producer_signer))
    aio.run(handle._process_command(int_name, cmd_name, b'\xff\xff', sig_ptrs, reply,
                                    {'deadline': timestamp() + 10000}))
    app.make_data.assert_called_once_with(int_name, None, handle.signer, content_type=ContentType.NACK)
    reply.assert_called_once_with(app.make_data.return_value)


def test_ingest_replies_are_signed_by_repo():
    app = Mock()
    repo_signer = Mock()
    keychain = Mock()
    keychain.get_signer.return_value = repo_signer
    handle = DirectIngestHandle(app, Mock(), {}, Mock(), command_validator=Mock(), keychain=keychain)
    assert handle.signer is repo_signer

    # end_block_id < start_block_id is malformed: NACK without fetching
    param = ObjParam()
    param.name = Name.from_str('/data')
    param.start_block_id = 2
    param.end_block_id = 1
    int_name = Name.from_str('/repo/ingest')
    reply = Mock()
    aio.run(handle._process_insert(int_name, param, reply, timestamp() + 10000))
    app.express.assert_not_called()
    app.make_data.assert_called_once_with(int_name, None, repo_signer, content_type=ContentType.NACK)
    reply.assert_called_once_with(app.make_data.return_value)


def test_ingest_route_is_not_registered_without_validator():
    app = Mock()
    app.register = AsyncMock()
    handle = DirectIngestHandle(app, Mock(), {}, Mock())

    aio.run(handle.listen(Name.from_str('/repo')))

    app.register.assert_not_awaited()
    app.attach_handler.assert_not_called()


def test_ingest_route_accepts_only_unsigned_interests():
    app = Mock()
    handle = listening_handle(app)

    ingest_prefix = Name.from_str('/repo/ingest')
    app.attach_handler.assert_called_once_with(ingest_prefix, handle._on_insert_interest,
                                               handle._accept_unsigned_interest)
    app.register.assert_awaited_once_with(ingest_prefix)

    def interest_sig(signer):
        wire = make_interest(ingest_prefix, InterestParam(lifetime=10000), b'\x06\x00', signer=signer)
        int_name, _, _, sig_ptrs = parse_interest(wire)
        return int_name, sig_ptrs

    # The command Data is validated later; the Interest carrying it must be unsigned
    int_name, sig_ptrs = interest_sig(None)
    assert aio.run(handle._accept_unsigned_interest(int_name, sig_ptrs, {})) == ValidResult.ALLOW_BYPASS
    int_name, sig_ptrs = interest_sig(DigestSha256Signer(for_interest=True))
    assert aio.run(handle._accept_unsigned_interest(int_name, sig_ptrs, {})) == ValidResult.FAIL
