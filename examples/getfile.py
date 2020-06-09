#!/usr/bin/env python3
"""
    NDN Repo getfile example.

    @Author jonnykong@cs.ucla.edu
"""

import argparse
import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, TlvModel, NameField
from ndn.security import KeychainDigest
from ndn_python_repo.clients import GetfileClient
from ndn.utils import gen_nonce
from ndn.types import InterestNack, InterestTimeout


class CatalogRequestParameter(TlvModel):
    """
    The data mapping fetch request from a client.
    """
    data_name = NameField()


async def run_getfile_client(app: NDNApp, **kwargs):
    """
    Async helper function to run the GetfileClient.
    This function is necessary because it's responsible for calling app.shutdown().
    """
    cmd_param = CatalogRequestParameter()
    cmd_param.data_name = kwargs['name_at_repo']
    cmd_param_bytes = cmd_param.encode()
    repo_name = ""
    name = kwargs['catalog']
    name += ['query']
    name += [str(gen_nonce())]
    logging.debug("Sending interest to {}".format(Name.to_str(name)))
    repo_names = []
    try:
        _, _, data_bytes = await app.express_interest(
                name, app_param=cmd_param_bytes, must_be_fresh=True, can_be_prefix=False, lifetime=4000)
        if bytes(data_bytes).decode('utf-8') != "":
            repo_names = bytes(data_bytes).decode('utf-8').split("|")

        logging.debug("Data Recvd: {}".format(repo_name))
    except InterestNack:
        logging.debug("NACK Received")
    except InterestTimeout:
        logging.debug("Interest Timeout")

    # for now the implementation just tries the first repo received needs to be changed to try all repos
    print("Trying for repo:", repo_name)
    client = GetfileClient(app, repo_name)
    await client.fetch_file(kwargs['name_at_repo'])

    app.shutdown()


def main():
    parser = argparse.ArgumentParser(description='getfile')
    parser.add_argument('-c', '--catalog',
                        required=True, help='Prefix of catalog')
    parser.add_argument('-n', '--name_at_repo',
                        required=True, help='Name used to store file at Repo')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.DEBUG)

    app = NDNApp()
    try:
        app.run_forever(
            after_start=run_getfile_client(app,
                                           catalog=Name.from_str(args.catalog),
                                           name_at_repo=Name.from_str(args.name_at_repo)))
    except FileNotFoundError:
        print('Error: could not connect to NFD.')



if __name__ == '__main__':
    main()
