"""
    NDN Repo delete client.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-09-26
"""

import os, sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import argparse
import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, Component
from pyndn.encoding import ProtobufTlv
from ndn.types import InterestNack, InterestTimeout
from command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from command.repo_command_response_pb2 import RepoCommandResponseMessage
from command_checker import CommandChecker


class DeleteClient(object):
    """
    This client deletes specified data packets stored at a remote repo.
    """
    def __init__(self, app: NDNApp, repo_name):
        """
        :param app: NDNApp.
        :param repo_name: NonStrictName. Routable name to remote repo.
        """
        self.app = app
        self.repo_name = repo_name

    async def delete_file(self, prefix, start_block_id: int, end_block_id: int):
        """
        Delete data packets between [<name_at_repo>/<start_block_id>, <name_at_repo>/<end_block_id>]
        from the remote repo.
        :param prefix: NonStrictName. The name with which this file is stored in the repo.
        :param start_block_id: int.
        :param end_block_id: int.
        """
        # Send command interest
        cmd_param = RepoCommandParameterMessage()
        for compo in Name.normalize(prefix):
            compo_bytes = Component.get_value(compo).tobytes()
            try:
                cmd_param.repo_command_parameter.name.component.append(compo_bytes)
            except Exception as e:
                print(e)
                return
        cmd_param.repo_command_parameter.start_block_id = start_block_id
        cmd_param.repo_command_parameter.end_block_id = end_block_id
        cmd_param_bytes = ProtobufTlv.encode(cmd_param).toBytes()

        # Send cmd interests to repo
        name = self.repo_name[:]
        name.append('delete')
        name.append(cmd_param_bytes)
        try:
            name_str = Name.to_str(Name.normalize(name))
            logging.info(f'Expressing interest: {Name.to_str(Name.normalize(name))}')
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
        cmd_response = RepoCommandResponseMessage()
        try:
            ProtobufTlv.decode(cmd_response, content)
        except RuntimeError as exc:
            logging.warning('Response decoding failed', exc)
            return
        process_id = cmd_response.repo_command_response.process_id
        status_code = cmd_response.repo_command_response.status_code
        logging.info(f'cmd_response process {process_id} accepted: status code {status_code}')

        # Send delete check interest wait until delete process completes
        checker = CommandChecker(self.app)
        while True:
            response = await checker.check_delete(self.repo_name, process_id)
            if response is None or response.repo_command_response.status_code == 300:
                logging.info(f'Response code is {response.repo_command_response.status_code}')
                await aio.sleep(1)
            elif response.repo_command_response.status_code == 200:
                logging.info('Delete process {} status: {}, delete_num: {}'
                             .format(process_id,
                                     response.repo_command_response.status_code,
                                     response.repo_command_response.delete_num))
                break
            else:
                # Shouldn't get here
                print('ASSERT FALSE, status = {}'.format(response.repo_command_response.status_code))
                assert False


async def run_delete_client(app: NDNApp, **kwargs):
    """
    Async helper function to run the DeleteClient.
    This function is necessary because it's responsible for calling app.shutdown().
    """
    client = DeleteClient(app, Name.from_str(kwargs['repo_name']))
    await client.delete_file(Name.from_str(kwargs['prefix']),
                             int(kwargs['start_block_id']),
                             int(kwargs['end_block_id']))
    app.shutdown()


def main():
    parser = argparse.ArgumentParser(description='putfile')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-p', '--prefix',
                        required=True, help='Prefix of data')
    parser.add_argument('-s', '--start_block_id',
                        required=True, help='Start Block ID')
    parser.add_argument('-e', '--end_block_id',
                        required=True, help='End Block ID')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    app = NDNApp()
    app.run_forever(
        after_start=run_delete_client(app, repo_name=args.repo_name,
                                      prefix=args.prefix,
                                      start_block_id=args.start_block_id,
                                      end_block_id=args.end_block_id))


if __name__ == '__main__':
    main()