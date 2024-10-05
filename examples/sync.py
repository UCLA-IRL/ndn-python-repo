#!/usr/bin/env python3
import argparse
import logging
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ndn_python_repo.clients import SyncClient


async def run_sync_client(app: NDNApp, **kwargs):
    client = SyncClient(app=app, prefix=kwargs['client_prefix'], repo_name=kwargs['repo_name'])
    await client.join_sync(sync_prefix=kwargs['sync_prefix'], register_prefix=kwargs['register_prefix'], 
                           data_name_dedupe=kwargs['data_name_dedupe'],
                           reset=kwargs['reset'])
    app.shutdown()


def main():
    parser = argparse.ArgumentParser(description='sync')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('--client_prefix', required=True,
                        help='prefix of this client')
    parser.add_argument('--sync_prefix', required=True,
                        help='The sync prefix repo should join')
    parser.add_argument('--register_prefix', required=False,
                        help='The prefix repo should register')
    parser.add_argument('--data_name_dedupe', required=False, default=False,
                        help='whether repo should dedupe the sync group in data naming')
    parser.add_argument('--reset', required=False, default=False,
                        help='whether repo should reset the sync group')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.DEBUG)

    app = NDNApp(face=None, keychain=KeychainDigest())
    register_prefix = None
    if args.register_prefix:
        register_prefix = Name.from_str(args.register_prefix)
    try:
        app.run_forever(
            after_start=run_sync_client(app, repo_name=Name.from_str(args.repo_name),
                                        client_prefix=Name.from_str(args.client_prefix),
                                        sync_prefix=Name.from_str(args.sync_prefix),
                                        register_prefix=register_prefix,
                                        data_name_dedupe=args.data_name_dedupe,
                                        reset=args.reset))
    except FileNotFoundError:
        print('Error: could not connect to NFD.')


if __name__ == '__main__':
    main()
