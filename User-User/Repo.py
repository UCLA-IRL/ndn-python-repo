from ndn_python_repo.cmd import controller
from typing import Optional
from ndn.app import NDNApp
from ndn.encoding import Name, InterestParam, BinaryStr, FormalName, MetaInfo, SignaturePtrs, SignatureType, Component, Signer
from ndn.app_support.security_v2 import parse_certificate

app = NDNApp()
repo_name = 'repo_name'
app.keychain.touch_identity(repo_name)

@app.route('/' + repo_name+'/certify/', need_sig_ptrs=True)
def on_interest(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr], sig_ptrs: SignaturePtrs):
    print(f'>> I: {Name.to_str(name)}, {param}, {bytes(_app_param)}')
    cert = parse_certificate(_app_param)
    identity = Name.to_str(cert.name[:])
    certified = False
    if identity == 'alice':
        certified = True

    if certified == False:
        content = "Authentication failed".encode()
        app.put_data(name, content=content, freshness_period=10000, identity=repo_name)
    else:
        # need to sign the data and return.
        cert = app.keychain.__getitem__('/' + repo_name+'/' +identity).default_key().default_cert().data
        content = cert
        app.put_raw_packet(cert)


    print(f'<< D: {Name.to_str(name)}')
    print(MetaInfo(freshness_period=10000))
    print(f'Content: (size: {len(content)})')
    print('')

# Certificate is hosting under this prefix
@app.route('/' + repo_name+'/KEY')
def on_interest(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr]):
    print(f'>> I: {Name.to_str(name)}, {param}')

    cert = app.keychain.__getitem__(repo_name).default_key().default_cert().data
    app.put_raw_packet(cert)

    # helper function
    cert = parse_certificate(cert)
    print(f'<< D: {Name.to_str(cert.name[:])}')
    print('')

if __name__ == '__main__':
    controller_setup = controller.setup_cert(repo_name)
    if controller_setup != True:
        print(f'Unsuccessful controller setup: {repo_name}')
    else:
        print(f'Successful controller setup: {repo_name}')
    app.run_forever()