#!/usr/bin/env python3
"""
    NDN Repo ingest example.

    @Author regmisuravi@gmail.com
"""

import argparse
import logging
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ndn_python_repo.clients import IngestClient
import uuid


async def run_ingest_client(app: NDNApp, **kwargs):
    """
    Async helper function to run the IngestClient.
    This function is necessary because it's responsible for calling app.shutdown().
    """
    client = IngestClient(app=app,
                          prefix=kwargs['client_prefix'],
                          repo_name=kwargs['repo_name'])
    success = await client.ingest_data(data_name=kwargs['data_name'],
                                       content=kwargs['content'],
                                       freshness_period=kwargs['freshness_period'],
                                       forwarding_hint=kwargs['forwarding_hint'],
                                       register_prefix=kwargs['register_prefix'])
    print('Ingest acknowledged by repo' if success else 'Ingest failed')
    app.shutdown()


def main():
    parser = argparse.ArgumentParser(description='ingest a single Data packet into the repo')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-n', '--data_name',
                        required=True, help='Name of the Data packet to ingest')
    parser.add_argument('-c', '--content',
                        required=True, help='Content of the Data packet')
    parser.add_argument('--client_prefix',
                        required=False, default='/ingest_client' + uuid.uuid4().hex.upper()[0:6],
                        help='prefix of this client')
    parser.add_argument('--freshness_period', type=int,
                        required=False, default=0,
                        help='Data packet\'s freshness period')
    parser.add_argument('--forwarding_hint', default=None,
                        help='Forwarding hint used by the repo when fetching data')
    parser.add_argument('--register_prefix', default=None,
                        help='The prefix repo should register (defaults to data_name)')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    # ``register_prefix`` is by default identical to ``data_name``
    if args.register_prefix is None:
        args.register_prefix = args.data_name
    args.register_prefix = Name.from_str(args.register_prefix)
    if args.forwarding_hint:
        args.forwarding_hint = Name.from_str(args.forwarding_hint)

    app = NDNApp(face=None, keychain=KeychainDigest())
    try:
        app.run_forever(
            after_start=run_ingest_client(app,
                                          repo_name=Name.from_str(args.repo_name),
                                          data_name=Name.from_str(args.data_name),
                                          content=args.content.encode(),
                                          client_prefix=Name.from_str(args.client_prefix),
                                          freshness_period=args.freshness_period,
                                          forwarding_hint=args.forwarding_hint,
                                          register_prefix=args.register_prefix))
    except FileNotFoundError:
        print('Error: could not connect to NFD.')


if __name__ == '__main__':
    main()
