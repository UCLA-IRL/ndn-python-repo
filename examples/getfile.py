"""
    NDN Repo getfile example.

    @Author jonnykong@cs.ucla.edu
    @Date   2020-01-14
"""

import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ndn_python_repo.clients import GetfileClient


async def main(app):
    repo_name = Name.from_str('testrepo')
    file_name_at_repo = Name.from_str('test.pdf')

    c = GetfileClient(app=app, repo_name=repo_name)
    await c.fetch_file(file_name_at_repo)

    app.shutdown()


if __name__ == '__main__':
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)
    app = NDNApp(face=None, keychain=KeychainDigest())
    app.run_forever(
        after_start=main(app))