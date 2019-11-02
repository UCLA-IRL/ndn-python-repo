"""
    NDN Repo insert check tester.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-09-23
"""

import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import argparse
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, Component, TlvModel, DecodeError
from ndn.types import InterestNack, InterestTimeout
from command.repo_commands import RepoCommandParameter, RepoCommandResponse


class CommandChecker(object):
    """
    Client for sending insert check interests.
    Users can create an CommandChecker instance to check for the status code.
    """
    def __init__(self, app: NDNApp):
        self.app = app
    
    async def check_insert(self, repo_name, process_id: int) -> RepoCommandResponse:
        return await self._check('insert', repo_name, process_id)
    
    async def check_delete(self, repo_name, process_id: int) -> RepoCommandResponse:
        return await self._check('delete', repo_name, process_id)

    async def _check(self, method: str, repo_name, process_id: int) -> RepoCommandResponse:
        """
        Return parsed insert check response message.
        # TODO: Use command interests instead of regular interests
        """
        cmd_param = RepoCommandParameter()
        cmd_param.process_id = process_id
        cmd_param_bytes = cmd_param.encode()

        name = repo_name[:]
        name.append(method + ' check')
        name.append(Component.from_bytes(cmd_param_bytes))

        try:
            print(f'Expressing interest: {Name.to_str(Name.normalize(name))}')
            data_name, meta_info, content = await self.app.express_interest(
                name, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
            print(f'Received data name: {Name.to_str(data_name)}')
        except InterestNack as e:
            print(f'Nacked with reason={e.reason}')
            return None
        except InterestTimeout:
            print(f'Timeout: {Name.to_str(Name.normalize(name))}')
            return None

        try:
            cmd_response = RepoCommandResponse.parse(content)
        except DecodeError as exc:
            logging.warning('Response blob decoding failed')
            return None
        except Exception as e:
            print(e)
        return cmd_response


async def run_check(app: NDNApp, **kwargs):
    """
    Async helper function to run the CommandChecker.
    This function is necessary because it's responsible for calling app.shutdown().
    """
    client = CommandChecker(app)
    response = await client.check_insert(kwargs['repo_name'], kwargs['process_id'])
    if response:
        status_code = response.status_code
        print('Status Code: {}'.format(status_code))
    app.shutdown()


def main():
    parser = argparse.ArgumentParser(description='segmented insert client')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-p', '--process_id',
                        required=True, help="Process ID")
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    app = NDNApp()
    app.run_forever(after_start=run_check(app, repo_name=Name.from_str(args.repo_name), process_id=int(args.process_id)))


if __name__ == '__main__':
    main()