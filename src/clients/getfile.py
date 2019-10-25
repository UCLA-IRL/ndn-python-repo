"""
    NDN Repo getfile client.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-10-24
"""

import os
import sys
import argparse
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name
from concurrent_fetcher import concurrent_fetcher


class GetfileClient(object):
    """
    This client fetches a file from the repo, and save it to working directory.
    """
    def __init__(self, app: NDNApp, repo_name):
        """
        :param app: NDNApp
        :param repo_name: Routable name to remote table
        """
        self.app = app
        self.repo_name = repo_name

    async def fetch_file(self, name_at_repo):
        """
        Fetch a file from remote repo, and write to disk.
        :param name_at_repo: The name with which this file is stored in the repo.
        """
        semaphore = aio.Semaphore(10)
        b_array = bytearray()
        async for (data_name, meta_info, content) in concurrent_fetcher(self.app, name_at_repo, 0, None, semaphore):
            b_array.extend(content)

        if len(b_array) > 0:
            filename = Name.to_str(name_at_repo)
            filename = filename.strip().split('/')[-1]
            logging.info(f'Fetching completed, writing to file {filename}')
            with open(filename, 'wb') as f:
                f.write(b_array)


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

