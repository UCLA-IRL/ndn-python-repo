#!/usr/bin/env python3
"""
    NDN Repo command checker example.

    @Author jonnykong@cs.ucla.edu
"""

import argparse
import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ndn_python_repo.clients import CommandChecker


async def run_check(app: NDNApp, **kwargs):
    """
    Async helper function to run the CommandChecker.
    This function is necessary because it's responsible for calling app.shutdown().
    """
    client = CommandChecker(app)
    response = await client.check_insert(kwargs['repo_name'], kwargs['process_id'])
    if response:
        status_code = response.status_code
        print('Status Code: {}'.format(status_code))
    app.shutdown()


def main():
    parser = argparse.ArgumentParser(description='segmented insert client')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-p', '--process_id',
                        required=True, help='Process ID')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    app = NDNApp()
    try:
        app.run_forever(
            after_start=run_check(app,
                                repo_name=Name.from_str(args.repo_name),
                                process_id=int(args.process_id)))
    except FileNotFoundError:
        print('Error: could not connect to NFD.')


if __name__ == '__main__':
    main()
