"""
    NDN Repo putfile client.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-10-18
"""

import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import argparse
import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, Component, DecodeError
from ndn.types import InterestNack, InterestTimeout
from .command_checker import CommandChecker
from ..command.repo_commands import RepoCommandParameter, RepoCommandResponse
from ndn.security import KeychainDigest


MAX_BYTES_IN_DATA_PACKET = 2000


class PutfileClient(object):
    """
    This client serves random segmented data
    """
    def __init__(self, app: NDNApp, repo_name):
        """
        :param app: NDNApp
        :param repo_name: NonStrictName. Routable name to remote repo.
        """
        self.app = app
        self.repo_name = repo_name
        self.name_str_to_data = dict()

    def _prepare_data(self, file_path: str, name_at_repo) -> int:
        """
        Shard file into data packets.
        :param file_path: Local FS path to file to insert
        :param name_at_repo: Name used to store file at repo
        :return: Number of packets required to send this file
        """
        if not os.path.exists(file_path):
            logging.error(f'file {file_path} does not exist')
            return 0
        with open(file_path, 'rb') as binary_file:
            b_array = bytearray(binary_file.read())
        if len(b_array) == 0:
            logging.warning("File is empty")
            return 0

        num_packets = int((len(b_array) - 1) / MAX_BYTES_IN_DATA_PACKET + 1)
        logging.info(f'There are {num_packets} packets in total')
        seq = 0
        for i in range(0, len(b_array), MAX_BYTES_IN_DATA_PACKET):
            content = b_array[i : min(i + MAX_BYTES_IN_DATA_PACKET, len(b_array))]
            name = name_at_repo[:]
            name.append(str(seq))
            packet = self.app.prepare_data(name, content, 
                final_block_id=Component.from_sequence_num(num_packets - 1),
                freshness_period=1000000)
            self.name_str_to_data[Name.to_str(name)] = packet
            seq += 1
        return num_packets

    def _on_interest(self, int_name, _int_param, _app_param):
        logging.info(f'On interest: {Name.to_str(int_name)}')
        if Name.to_str(int_name) in self.name_str_to_data:
            self.app.put_raw_packet(self.name_str_to_data[Name.to_str(int_name)])
            logging.info(f'Serve data: {Name.to_str(int_name)}')
        else:
            logging.info(f'Data does not exist: {Name.to_str(int_name)}')

    async def insert_file(self, file_path: str, name_at_repo):
        """
        Insert a file to remote repo.
        :param file_path: Local FS path to file to insert
        :param name_at_repo: Name used to store file at repo
        """
        num_packets = self._prepare_data(file_path, name_at_repo)
        if num_packets == 0:
            return
        # Register prefix for responding interests from repo
        # self.app.route(name_at_repo)(self._on_interest)
        await self.app.register(name_at_repo, self._on_interest)

        cmd_param = RepoCommandParameter()
        cmd_param.name = name_at_repo
        cmd_param.start_block_id = 0
        cmd_param.end_block_id = num_packets - 1
        cmd_param_bytes = cmd_param.encode()

        # Send cmd interest to repo
        name = self.repo_name[:]
        name.append('insert')
        name.append(Component.from_bytes(cmd_param_bytes))

        try:
            logging.info(f'Expressing interest: {Name.to_str(name)}')
            data_name, meta_info, content = await self.app.express_interest(
                name, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
            logging.info(f'Received data name: {Name.to_str(data_name)}')
        except InterestNack as e:
            logging.warning(f'Nacked with reason: {e.reason}')
            return
        except InterestTimeout:
            logging.warning(f'Timeout')
            return

        # Parse response from repo
        try:
            cmd_response = RepoCommandResponse.parse(content)
        except DecodeError as exc:
            logging.warning('Response blob decoding failed')
            return
        process_id = cmd_response.process_id
        status_code = cmd_response.status_code
        logging.info(f'cmd_response process {process_id} accepted: status code {status_code}')

        # Send insert check interest to wait until insert process completes
        checker = CommandChecker(self.app)
        while True:
            response = await checker.check_insert(self.repo_name, process_id)
            if response is None:
                logging.info(f'Response code is None')
                await aio.sleep(1)
            elif response.status_code == 300:
                logging.info(f'Response code is {response.status_code}')
                await aio.sleep(1)
            elif response.status_code == 200:
                logging.info('Insert process {} status: {}, insert_num: {}'
                             .format(process_id,
                                     response.status_code,
                                     response.insert_num))
                break
            else:
                # Shouldn't get here
                assert False


async def run_putfile_client(app: NDNApp, **kwargs):
    """
    Async helper function to run the PutfileClient.
    This function is necessary because it's responsible for calling app.shutdown().
    """
    client = PutfileClient(app, Name.from_str(kwargs['repo_name']))
    await client.insert_file(kwargs['file_path'], Name.from_str(kwargs['name_at_repo']))
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
    app.run_forever(
        after_start=run_putfile_client(app, repo_name=args.repo_name,
                                       file_path=args.file_path,
                                       name_at_repo=args.name_at_repo))


if __name__ == "__main__":
    main()

