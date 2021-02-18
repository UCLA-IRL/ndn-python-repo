# -----------------------------------------------------------------------------
# NDN Repo insert check tester.
#
# @Author jonnykong@cs.ucla.edu
# @Date   2019-09-23
# -----------------------------------------------------------------------------

import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import argparse
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName, Component, TlvModel, DecodeError
from ndn.types import InterestNack, InterestTimeout
from ..command.repo_commands import RepoCommandParameter, RepoCommandResponse


class CommandChecker(object):
    def __init__(self, app: NDNApp):
        """
        This client sends check interests to the repo.

        :param app: NDNApp.
        """
        self.app = app
    
    async def check_insert(self, repo_name: NonStrictName, process_id: int) -> RepoCommandResponse:
        """
        Check the status of an insert process.

        :param repo_name: NonStrictName. The name of the remote repo.
        :param process_id: int. The process id of the process to check.
        :return: The response from the repo.
        """
        return await self._check('insert', repo_name, process_id)
    
    async def check_delete(self, repo_name, process_id: int) -> RepoCommandResponse:
        """
        Check the status of a delete process.

        :param repo_name: NonStrictName. The name of the remote repo.
        :param process_id: int. The process id of the process to check.
        :return: The response from the repo.
        """
        return await self._check('delete', repo_name, process_id)

    async def _check(self, method: str, repo_name: NonStrictName,
                     process_id: int) -> RepoCommandResponse:
        """
        Return parsed insert check response message.

        :param method: str. One of `insert` or `delete`.
        :param repo_name: NonStrictName. The name of the remote repo.
        :param process_id: int. The process id of the process to check.
        # TODO: Use command interests instead of regular interests
        """
        cmd_param = RepoCommandParameter()
        cmd_param.process_id = process_id
        cmd_param_bytes = cmd_param.encode()

        name = repo_name[:]
        name.append(method + ' check')
        name.append(Component.from_bytes(cmd_param_bytes))

        try:
            logging.info(f'Expressing interest: {Name.to_str(name)}')
            data_name, meta_info, content = await self.app.express_interest(
                name, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
            logging.info(f'Received data name: {Name.to_str(data_name)}')
        except InterestNack as e:
            logging.info(f'Nacked with reason={e.reason}')
            return None
        except InterestTimeout:
            logging.info(f'Timeout: {Name.to_str(name)}')
            return None

        try:
            cmd_response = RepoCommandResponse.parse(content)
        except DecodeError as exc:
            logging.warning('Response blob decoding failed')
            return None
        except Exception as e:
            logging.warning(e)
        return cmd_response