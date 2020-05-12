#!/usr/bin/env python3
"""
    NDN Repo putfile example.

    @Author jonnykong@cs.ucla.edu
"""

import argparse
import asyncio as aio
import logging
import multiprocessing
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ndn_python_repo.clients import PutfileClient


async def run_putfile_client(app: NDNApp, **kwargs):
    """
    Async helper function to run the PutfileClient.
    This function is necessary because it's responsible for calling app.shutdown().
    """
    client = PutfileClient(app, kwargs['client_prefix'], kwargs['repo_name'])
    await client.insert_file(kwargs['file_path'], kwargs['name_at_repo'], kwargs['segment_size'],
                           kwargs['freshness_period'], kwargs['cpu_count'])
    app.shutdown()


def main():
    parser = argparse.ArgumentParser(description='putfile')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-f', '--file_path',
                        required=True, help='Path to input file')
    parser.add_argument('-n', '--name_at_repo',
                        required=True, help='Prefix used to store file at Repo')
    parser.add_argument('--client_prefix',
                        required=False, default='/putfile_client',
                        help='prefix of this client')
    parser.add_argument('--segment_size', type=int,
                        required=False, default=8000,
                        help='Size of each data packet')
    parser.add_argument('--freshness_period', type=int,
                        required=False, default=0,
                        help='Data packet\'s freshness period')
    parser.add_argument('--cpu_count', type=int,
                        required=False, default=multiprocessing.cpu_count(),
                        help='Number of cores to use')
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
                                           name_at_repo=Name.from_str(args.name_at_repo),
                                           client_prefix=Name.from_str(args.client_prefix),
                                           segment_size=args.segment_size,
                                           freshness_period=args.freshness_period,
                                           cpu_count=args.cpu_count))
    except FileNotFoundError:
        print('Error: could not connect to NFD.')


if __name__ == '__main__':
    main()
