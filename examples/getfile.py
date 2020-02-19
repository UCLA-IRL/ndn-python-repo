"""
    NDN Repo getfile example.

    @Author jonnykong@cs.ucla.edu
    @Date   2020-01-14
"""

import argparse
import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ndn_python_repo.clients import GetfileClient


async def run_getfile_client(app: NDNApp, **kwargs):
    """
    Async helper function to run the GetfileClient.
    This function is necessary because it's responsible for calling app.shutdown().
    """
    client = GetfileClient(app, Name.from_str(kwargs['repo_name']))
    await client.fetch_file(Name.from_str(kwargs['name_at_repo']))
    app.shutdown()


def main():
    parser = argparse.ArgumentParser(description='getfile')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-n', '--name_at_repo',
                        required=True, help='Name used to store file at Repo')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    app = NDNApp()
    app.run_forever(
        after_start=run_getfile_client(app, repo_name=args.repo_name,
                                       name_at_repo=args.name_at_repo))


if __name__ == "__main__":
    main()