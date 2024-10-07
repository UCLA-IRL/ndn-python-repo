# -----------------------------------------------------------------------------
# NDN Repo delete client.
#
# @Author jonnykong@cs.ucla.edu
# @Date   2019-09-26
# -----------------------------------------------------------------------------

import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import asyncio as aio
from ..command import RepoCommandParam, ObjParam, EmbName, RepoStatCode
from .command_checker import CommandChecker
from ..utils import PubSub
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName
from typing import Optional
from hashlib import sha256


class DeleteClient(object):
    def __init__(self, app: NDNApp, prefix: NonStrictName, repo_name: NonStrictName):
        """
        This client deletes data packets from the remote repo.

        :param app: NDNApp.
        :param repo_name: NonStrictName. Routable name to remote repo.
        """
        self.app = app
        self.prefix = prefix
        self.repo_name = Name.normalize(repo_name)
        self.pb = PubSub(self.app, self.prefix)
        self.logger = logging.getLogger(__name__)

    async def delete_file(self, prefix: NonStrictName, start_block_id: int = 0,
                          end_block_id: int = None,
                          register_prefix: Optional[NonStrictName] = None,
                          check_prefix: Optional[NonStrictName] = None) -> int:
        """
        Delete from repo packets between "<name_at_repo>/<start_block_id>" and\
            "<name_at_repo>/<end_block_id>" inclusively.

        :param prefix: NonStrictName. The name of the file stored in the remote repo.
        :param start_block_id: int. Default value is 0.
        :param end_block_id: int. If not specified, repo will attempt to delete all data packets\
            with segment number starting from `start_block_id` continuously.
        :param register_prefix: If repo is configured with ``register_root=False``, it unregisters\
            ``register_prefix`` after receiving the deletion command.
        :param check_prefix: NonStrictName. The repo will publish process check messages under\
            ``<check_prefix>/check``. It is necessary to specify this value in the param, instead\
            of using a predefined prefix, to make sure the subscriber can register this prefix\
            under the NDN prefix registration security model. If not specified, default value is\
            the client prefix.
        :return: Number of deleted packets.
        """
        # send command interest
        cmd_param = RepoCommandParam()
        cmd_obj = ObjParam()
        cmd_param.objs = [cmd_obj]
        cmd_obj.name = prefix
        cmd_obj.start_block_id = start_block_id
        cmd_obj.end_block_id = end_block_id
        cmd_obj.register_prefix = EmbName()
        cmd_obj.register_prefix.name = register_prefix

        cmd_param_bytes = bytes(cmd_param.encode())
        request_no = sha256(cmd_param_bytes).digest()

        # publish msg to repo's delete topic
        await self.pb.wait_for_ready()
        is_success = await self.pb.publish(self.repo_name + Name.from_str('delete'), cmd_param_bytes)
        if is_success:
            self.logger.info('Published an delete msg and was acknowledged by a subscriber')
        else:
            self.logger.info('Published an delete msg but was not acknowledged by a subscriber')

        # wait until repo delete all data
        delete_num = 0
        if is_success:
            delete_num = await self._wait_for_finish(check_prefix, request_no)
        return delete_num

    async def _wait_for_finish(self, check_prefix: NonStrictName, request_no: bytes):
        """
        Send delete check interest to wait until delete process completes

        :param check_prefix: NonStrictName. The prefix under which the check message will be\
            published.
        :param request_no: int. The request number to check for delete process (formerly process id)
        :return: Number of deleted packets.
        """
        # fixme: why is check_prefix never used?
        checker = CommandChecker(self.app)
        n_retries = 3
        while n_retries > 0:
            response = await checker.check_delete(self.repo_name, request_no)
            if response is None:
                self.logger.info(f'No response')
                await aio.sleep(1)
            # might receive 404 if repo has not yet processed delete command msg
            elif response.status_code == RepoStatCode.NOT_FOUND:
                n_retries -= 1
                # self.logger.info(f'Deletion {request_no} not handled yet')
                await aio.sleep(1)
            elif response.status_code == RepoStatCode.IN_PROGRESS:
                self.logger.info(f'Deletion {request_no} in progress')
                await aio.sleep(1)
            elif response.status_code == RepoStatCode.COMPLETED:
                delete_num = 0
                for obj in response.objs:
                    delete_num += obj.delete_num
                self.logger.info(f'Deletion request {request_no} complete, delete_num: {delete_num}')
                return delete_num
            elif response.status_code == RepoStatCode.FAILED:
                self.logger.info(f'Deletion request {request_no} failed')
            else:
                # Shouldn't get here
                self.logger.error(f'Received unrecognized status code {response.status_code}')
