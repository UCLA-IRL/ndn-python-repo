#!/usr/bin/env python3
"""
    NDN Repo putfile example.

    @Author jonnykong@cs.ucla.edu
"""

import argparse
import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ndn_python_repo.clients import PutfileClient


async def run_putfile_client(app: NDNApp, **kwargs):
    """
    Async helper function to run the PutfileClient.
    This function is necessary because it's responsible for calling app.shutdown().
    """
    client = PutfileClient(app, kwargs['repo_name'])
    await client.insert_file(kwargs['file_path'], kwargs['name_at_repo'])
    app.shutdown()


def main():
    parser = argparse.ArgumentParser(description='putfile')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-f', '--file_path',
                        required=True, help='Path to input file')
    parser.add_argument('-n', '--name_at_repo',
                        required=True, help='Name used to store file at Repo')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    app = NDNApp(face=None, keychain=KeychainDigest())
    try:
        app.run_forever(
            after_start=run_putfile_client(app,
                                        repo_name=Name.from_str(args.repo_name),
                                        file_path=args.file_path,
                                        name_at_repo=Name.from_str(args.name_at_repo)))
    except FileNotFoundError:
        print('Error: could not connect to NFD.')


if __name__ == '__main__':
    main()
