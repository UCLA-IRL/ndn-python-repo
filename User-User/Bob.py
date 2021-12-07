from typing import Optional
from ndn.app import NDNApp
from ndn.encoding import Name, InterestParam, BinaryStr, FormalName, MetaInfo, SignaturePtrs, SignatureType, Component, Signer
from ndn.app_support.security_v2 import parse_certificate
import logging
from CustomTLV import Model

app = NDNApp()
# Create identity on the machine local keychain
repo_name = 'repo_name'
user_name = 'bob'
Alice_cert = None
Repo_user_name = '/'+repo_name+'/'+user_name
app.keychain.touch_identity(user_name)

async def main():
    try:
        timestamp = ndn.utils.timestamp()
        name = Name.from_str('/'+repo_name+'/alice/certify') + [Component.from_timestamp(timestamp)]
        cert = app.keychain.touch_identity(user_name).default_key().default_cert().data
        send_cert = bytes(cert)
        cert = parse_certificate(cert)
        print(f'cert_name: {Name.to_str(cert.name[:])}')
        print(f'Sending Interest {Name.to_str(name)}, {InterestParam(must_be_fresh=True, lifetime=6000)}')
        # set a validator when requesting data
        data_name, meta_info, content = await app.express_interest(
            name, must_be_fresh=True, app_param=send_cert, can_be_prefix=False, lifetime=6000, validator=verify_ecdsa_signature)
        print(f'Received Data Name: {Name.to_str(data_name)}')
        print(meta_info)
        print(content if content else None)
        Bob_cert = content
        #send it to Repo for cert. 

    except InterestNack as e:
        print(f'Nacked with reason={e.reason}')
    except InterestTimeout:
        print(f'Timeout')
    except InterestCanceled:
        print(f'Canceled')
    except ValidationFailure:
        print(f'Data failed to validate')
    finally:
        app.shutdown()

"""
This validator parses the key name from the signature info, expresses interest to fetch corresponding certificates, then use fetched 
certificate to verify Data's signature.

Certificate itself is a Data packet, TLV format specified in https://named-data.net/doc/ndn-cxx/current/specs/certificate-format.html
Certificate content contains an identity's public key, this validator extracts the public key from certificate and verify the original Data 
packet's signature.

Note: Completely validating a Data packet includes three steps:
      1. Validating if the signing idenity is authorized to produce this Data packet.
         We refer this as trust schema, determined by app.
      2. Verifying if the Data signature by signing identity's public key.
      3. Verifying signing identity's certificate against its issuer's public key.
         Validator should recursively does this until reach to its trust anchor.
      This validator only does step 2.
"""
async def verify_ecdsa_signature(name: FormalName, sig: SignaturePtrs) -> bool:
    sig_info = sig.signature_info
    covered_part = sig.signature_covered_part
    sig_value = sig.signature_value_buf
    if not sig_info or sig_info.signature_type != SignatureType.SHA256_WITH_ECDSA:
        return False
    if not covered_part or not sig_value:
        return False
    key_name = sig_info.key_locator.name[0:]
    print('Extract key_name: ', Name.to_str(key_name))
    print(f'Sending Interest {Name.to_str(key_name)}, {InterestParam(must_be_fresh=True, lifetime=6000)}')
    cert_name, meta_info, content, raw_packet = await app.express_interest(key_name, must_be_fresh=True, can_be_prefix=True,
                                                                           lifetime=6000, need_raw_packet=True)
    print('Fetched certificate name: ', Name.to_str(cert_name))
    # certificate itself is a Data packet
    cert = parse_certificate(raw_packet)
    # load public key from the data content
    key_bits = None
    try:
        key_bits = bytes(content)
    except (KeyError, Attri buteError):
        print('Cannot load pub key from received certificate')
        return False
    pk = ECC.import_key(key_bits)
    verifier = DSS.new(pk, 'fips-186-3', 'der')
    sha256_hash = SHA256.new()
    for blk in covered_part:
        sha256_hash.update(blk)
    try:
        verifier.verify(sha256_hash, bytes(sig_value))
    except ValueError:
        return False
    return True

if __name__ == '__main__':
    app.run_forever(after_start=main())