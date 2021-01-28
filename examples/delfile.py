#!/usr/bin/env python3
"""
    NDN Repo delfile example.

    @Author jonnykong@cs.ucla.edu
"""

import argparse
import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ndn_python_repo.clients import DeleteClient


async def run_delete_client(app: NDNApp, **kwargs):
    """
    Async helper function to run the DeleteClient.
    This function is necessary because it's responsible for calling app.shutdown().
    """
    client = DeleteClient(app=app,
                          prefix=kwargs['client_prefix'],
                          repo_name=kwargs['repo_name'])
    
    # Set pubsub to register ``check_prefix`` directly, so all prefixes under ``check_prefix`` will
    # be handled with interest filters. This reduces the number of registered prefixes at NFD, when
    # inserting multiple files with one client
    check_prefix = kwargs['client_prefix']
    client.pb.set_base_prefix(check_prefix)

    await client.delete_file(prefix=kwargs['name_at_repo'],
                             start_block_id=kwargs['start_block_id'],
                             end_block_id=kwargs['end_block_id'],
                             register_prefix=kwargs['register_prefix'],
                             check_prefix=check_prefix)
    app.shutdown()


def main():
    parser = argparse.ArgumentParser(description='delfile')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-n', '--name_at_repo',
                        required=True, help='Name used to store file at Repo')
    parser.add_argument('-s', '--start_block_id',
                        required=False, help='Start Block ID')
    parser.add_argument('-e', '--end_block_id',
                        required=False, help='End Block ID')
    parser.add_argument('--client_prefix',
                        required=False, default='/delfile_client',
                        help='prefix of this client')
    parser.add_argument('--register_prefix', default=None,
                        help='The prefix repo should register')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    # process default values
    start_block_id = int(args.start_block_id) if args.start_block_id else None
    end_block_id = int(args.end_block_id) if args.end_block_id else None
    if args.register_prefix == None:
        args.register_prefix = args.name_at_repo
    args.register_prefix = Name.from_str(args.register_prefix)

    app = NDNApp()

    try:
        app.run_forever(
            after_start=run_delete_client(app,
                                          repo_name=Name.from_str(args.repo_name),
                                          name_at_repo=Name.from_str(args.name_at_repo),
                                          start_block_id=start_block_id,
                                          end_block_id=end_block_id,
                                          client_prefix=Name.from_str(args.client_prefix),
                                          register_prefix=args.register_prefix))
    except FileNotFoundError:
        print('Error: could not connect to NFD.')


if __name__ == '__main__':
    main()
