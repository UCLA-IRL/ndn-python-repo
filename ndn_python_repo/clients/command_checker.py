# -----------------------------------------------------------------------------
# NDN Repo insert check tester.
#
# @Author jonnykong@cs.ucla.edu
# @Date   2019-09-23
# -----------------------------------------------------------------------------

import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import logging
from typing import Optional
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName, DecodeError
from ndn.types import InterestNack, InterestTimeout
from ..command.repo_commands import RepoStatQuery, RepoCommandRes


class CommandChecker(object):
    def __init__(self, app: NDNApp):
        """
        This client sends check interests to the repo.

        :param app: NDNApp.
        """
        self.app = app
        self.logger = logging.getLogger(__name__)
    
    async def check_insert(self, repo_name: NonStrictName, request_no: bytes) -> RepoCommandRes:
        """
        Check the status of an insert process.

        :param repo_name: NonStrictName. The name of the remote repo.
        :param request_no: bytes. The request id of the process to check.
        :return: The response from the repo.
        """
        return await self._check('insert', repo_name, request_no)
    
    async def check_delete(self, repo_name, request_no: bytes) -> RepoCommandRes:
        """
        Check the status of a delete process.

        :param repo_name: NonStrictName. The name of the remote repo.
        :param request_no: bytes. The request id of the process to check.
        :return: The response from the repo.
        """
        return await self._check('delete', repo_name, request_no)

    async def _check(self, method: str, repo_name: NonStrictName,
                     request_no: bytes) -> Optional[RepoCommandRes]:
        """
        Return parsed insert check response message.

        :param method: str. One of `insert` or `delete`.
        :param repo_name: NonStrictName. The name of the remote repo.
        :param request_no: bytes. The request id of the process to check.
        """
        cmd_param = RepoStatQuery()
        cmd_param.request_no = request_no
        cmd_param_bytes = cmd_param.encode()

        name = Name.normalize(repo_name)
        name += Name.from_str(method + ' check')

        try:
            self.logger.info(f'Expressing interest: {Name.to_str(name)}')
            data_name, meta_info, content = await self.app.express_interest(
                name, cmd_param_bytes, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
            self.logger.info(f'Received data name: {Name.to_str(data_name)}')
        except InterestNack as e:
            self.logger.info(f'Nacked with reason={e.reason}')
            return None
        except InterestTimeout:
            self.logger.info(f'Timeout: {Name.to_str(name)}')
            return None

        try:
            cmd_response = RepoCommandRes.parse(content)
            return cmd_response
        except DecodeError as exc:
            self.logger.warning(f'Response blob decoding failed for {exc}')
            return None
        except Exception as e:
            self.logger.warning(e)
            return None
