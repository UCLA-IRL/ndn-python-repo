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
from ndn.encoding import Name, Component
from ndn.types import InterestNack, InterestTimeout
from pyndn.encoding import ProtobufTlv
from command_checker import CommandChecker
from command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from command.repo_command_response_pb2 import RepoCommandResponseMessage

MAX_BYTES_IN_DATA_PACKET = 2000


class PutfileClient(object):
    """
    This client serves random segmented data
    """
    def __init__(self, app: NDNApp, repo_name):
        """
        :param app: NDNApp
        :param repo_name: Routable name to remote table
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
            packet = self.app.prepare_data(name, content, final_block_id=Component.from_sequence_num(num_packets - 1))
            self.name_str_to_data[Name.to_str(Name.normalize(name))] = packet
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

        # Prepare cmd param
        cmd_param = RepoCommandParameterMessage()
        name_normalized = Name.normalize(name_at_repo)
        for compo in name_normalized:
            compo_bytes = Component.get_value(compo).tobytes()
            try:
                cmd_param.repo_command_parameter.name.component.append(compo_bytes)
            except Exception as e:
                print(e)
        cmd_param.repo_command_parameter.start_block_id = 0
        cmd_param.repo_command_parameter.end_block_id = num_packets - 1
        cmd_param_bytes = ProtobufTlv.encode(cmd_param).toBytes()

        # Send cmd interest to repo
        name = self.repo_name[:]
        name.append('insert')
        name.append(cmd_param_bytes)
        try:
            name_str = Name.to_str(Name.normalize(name))
            print(name_str)
            print(f'Expressing interest: {Name.to_str(Name.normalize(name))}')
            data_name, meta_info, content = await self.app.express_interest(
                name, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
            print(f'Received data name: {Name.to_str(data_name)}')
        except InterestNack as e:
            print(f'Nacked with reason: {e.reason}')
            return
        except InterestTimeout:
            print(f'Timeout')
            return

        # Parse response from repo
        cmd_response = RepoCommandResponseMessage()
        try:
            ProtobufTlv.decode(cmd_response, content)
        except RuntimeError as exc:
            logging.warning('Response decoding failed', exc)
            return
        process_id = cmd_response.repo_command_response.process_id
        status_code = cmd_response.repo_command_response.status_code
        logging.info(f'cmd_response process {process_id} accepted: status code {status_code}')

        # Send insert check interest to wait until insert process completes
        checker = CommandChecker(self.app)
        while True:
            response = await checker.check_insert(self.repo_name, process_id)
            if response is None or response.repo_command_response.status_code == 300:
                print(f'Response code is {response.repo_command_response.status_code}')
                await aio.sleep(1)
            elif response.repo_command_response.status_code == 200:
                logging.info('Insert process {} status: {}, insert_num: {}'
                             .format(process_id,
                                     response.repo_command_response.status_code,
                                     response.repo_command_response.insert_num))
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

    app = NDNApp()
    app.run_forever(
        after_start=run_putfile_client(app, repo_name=args.repo_name,
                                       file_path=args.file_path,
                                       name_at_repo=args.name_at_repo))


if __name__ == "__main__":
    main()

