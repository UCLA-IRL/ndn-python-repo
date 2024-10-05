import argparse
import logging
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ndn_python_repo.clients import SyncClient

async def run_leave_sync_client(app: NDNApp, **kwargs):
    client = SyncClient(app=app, prefix=kwargs['client_prefix'], repo_name=kwargs['repo_name'])
    await client.leave_sync(sync_prefix=kwargs['sync_prefix'])
    app.shutdown()


def main():
    parser = argparse.ArgumentParser(description='leavesync')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('--client_prefix', required=True,
                        help='prefix of this client')
    parser.add_argument('--sync_prefix', required=True,
                        help='The sync prefix repo should leave')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.DEBUG)

    app = NDNApp(face=None, keychain=KeychainDigest())
    try:
        app.run_forever(
            after_start=run_leave_sync_client(app, repo_name=Name.from_str(args.repo_name),
                                        client_prefix=Name.from_str(args.client_prefix),
                                        sync_prefix=Name.from_str(args.sync_prefix)))
    except FileNotFoundError:
        print('Error: could not connect to NFD.')


if __name__ == '__main__':
    main()
