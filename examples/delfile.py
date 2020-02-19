"""
    NDN Repo delfile example.

    @Author jonnykong@cs.ucla.edu
    @Date   2020-02-18
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
    start_block_id = int(kwargs['start_block_id']) if kwargs['start_block_id'] != None else 0
    end_block_id = int(kwargs['end_block_id']) if kwargs['end_block_id'] != None else None

    client = DeleteClient(app, kwargs['repo_name'])
    await client.delete_file(kwargs['name_at_repo'],
                             start_block_id,
                             end_block_id)
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
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)
    
    start_block_id = int(args.start_block_id) if args.start_block_id else None
    end_block_id = int(args.end_block_id) if args.end_block_id else None

    app = NDNApp()
    app.run_forever(
        after_start=run_delete_client(app, 
                                      repo_name=Name.from_str(args.repo_name),
                                      name_at_repo=Name.from_str(args.name_at_repo),
                                      start_block_id=start_block_id,
                                      end_block_id=end_block_id))


if __name__ == '__main__':
    main()