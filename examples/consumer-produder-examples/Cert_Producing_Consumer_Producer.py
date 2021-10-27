from typing import Optional
from ndn.app import NDNApp
from ndn.encoding import Name, InterestParam, BinaryStr, FormalName, MetaInfo, SignaturePtrs, SignatureType, Component
from ndn.app_support.security_v2 import parse_certificate
import logging
from CustomTLV import Model

app = NDNApp()
# Create identity on the machine local keychain
app.keychain.touch_identity('/example/testApp')

@app.route('/example/testApp/randomData', need_sig_ptrs=True)
def on_interest(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr], sig_ptrs: SignaturePtrs):
    print(f'>> I: {Name.to_str(name)}, {param}, {bytes(_app_param)}')
    cert = parse_certificate(_app_param)
    model = Model()
    model.consumer_cert = _app_param
    model.producer_cert = sig_ptrs.signature_value_buf
    content = model.encode()

    # Signing identity is "/example/testApp"
    app.put_data(name, content=content, freshness_period=10000, identity='/example/testApp')
    print(f'<< D: {Name.to_str(name)}')
    print(MetaInfo(freshness_period=10000))
    print(f'Content: (size: {len(content)})')
    print('')

# Certificate is hosting under this prefix
@app.route('/example/testApp/KEY')
def on_interest(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr]):
    print(f'>> I: {Name.to_str(name)}, {param}')

    # get signing identity's default certificate (in most cases this is enough)
    cert = app.keychain.__getitem__('/example/testApp').default_key().default_cert().data
    # certificate itself is an NDN Data packet, so we return the raw certificate
    app.put_raw_packet(cert)

    # helper function
    cert = parse_certificate(cert)
    print(f'<< D: {Name.to_str(cert.name[:])}')
    print('')

if __name__ == '__main__':
    app.run_forever()