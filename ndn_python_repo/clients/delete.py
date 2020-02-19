"""
    NDN Repo delete client.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-09-26
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
from ..command.repo_commands import RepoCommandParameter, RepoCommandResponse
from .command_checker import CommandChecker


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
        cmd_param = RepoCommandParameter()
        cmd_param.name = prefix
        cmd_param.start_block_id = start_block_id
        cmd_param.end_block_id = end_block_id
        cmd_param_bytes = cmd_param.encode()

        # Send cmd interests to repo
        name = self.repo_name[:]
        name.append('delete')
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

        # Send delete check interest wait until delete process completes
        checker = CommandChecker(self.app)
        while True:
            response = await checker.check_delete(self.repo_name, process_id)
            if response is None:
                logging.info(f'Response code is None')
                await aio.sleep(1)
            elif response.status_code == 300:
                logging.info(f'Response code is {response.status_code}')
                await aio.sleep(1)
            elif response.status_code == 200:
                logging.info('Delete process {} status: {}, delete_num: {}'
                             .format(process_id, response.status_code, response.delete_num))
                break
            else:
                # Shouldn't get here
                assert False