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

    async def fetch_file(self, name_at_repo: NonStrictName, local_filename: str = None, overwrite=False):
        """
        Fetch a file from remote repo, and write to the current working directory.

        :param name_at_repo: NonStrictName. The name with which this file is stored in the repo.
        :param local_filename: str. The filename of the retrieved file on the local file system.
        :param overwrite: If true, existing files are replaced.
        """

        # If no local filename is provided, store file with last name component
        # of repo filename
        if local_filename is None:
            local_filename = Name.to_str(name_at_repo)
            local_filename = os.path.basename(local_filename)

        # If the file already exists locally and overwrite=False, retrieving the file makes no
        # sense.
        if os.path.isfile(local_filename) and not overwrite:
            raise FileExistsError("{} already exists".format(local_filename))


        semaphore = aio.Semaphore(10)
        b_array = bytearray()
        async for (_, _, content, _) in concurrent_fetcher(self.app, name_at_repo, 0, None, semaphore):
            b_array.extend(content)

        if len(b_array) > 0:

            logging.info(f'Fetching completed, writing to file {local_filename}')

            # Create folder hierarchy
            local_folder = os.path.dirname(local_filename)
            if local_folder:
                os.makedirs(local_folder, exist_ok=True)

            # Write retrieved data to file
            if os.path.isfile(local_filename) and overwrite:
                os.remove(local_filename)
            with open(local_filename, 'wb') as f:
                f.write(b_array)
