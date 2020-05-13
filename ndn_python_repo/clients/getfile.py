# -----------------------------------------------------------------------------
# NDN Repo getfile client.
#
# @Author jonnykong@cs.ucla.edu
# @Date   2019-10-24
# -----------------------------------------------------------------------------

import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName
from ..utils.concurrent_fetcher import concurrent_fetcher


class GetfileClient(object):
    """
    This client fetches a file from the repo, and save it to working directory.
    """
    def __init__(self, app: NDNApp, repo_name):
        """
        A client to retrieve files from the remote repo.

        :param app: NDNApp.
        :param repo_name: NonStrictName. Routable name to remote repo.
        """
        self.app = app
        self.repo_name = repo_name

    async def fetch_file(self, name_at_repo: NonStrictName):
        """
        Fetch a file from remote repo, and write to the current working directory.

        :param name_at_repo: NonStrictName. The name with which this file is stored in the repo.
        """
        semaphore = aio.Semaphore(10)
        b_array = bytearray()
        async for (_, _, content, _) in concurrent_fetcher(self.app, name_at_repo, 0, None, semaphore):
            b_array.extend(content)

        if len(b_array) > 0:
            filename = Name.to_str(name_at_repo)
            filename = filename.strip().split('/')[-1]
            logging.info(f'Fetching completed, writing to file {filename}')
            with open(filename, 'wb') as f:
                f.write(b_array)