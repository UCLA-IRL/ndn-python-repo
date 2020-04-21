import asyncio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, Component
from ndn.encoding.tlv_model import DecodeError

from ..storage import Storage
from ..command.repo_commands import RepoCommandParameter, RepoCommandResponse, PrefixesInStorage


class CommandHandle(object):
    """
    Interface for command interest handles
    """
    def __init__(self, app: NDNApp, storage: Storage):
        self.app = app
        self.storage = storage
        self.m_processes = dict()

    def listen(self, prefix: Name):
        raise NotImplementedError

    def on_check_interest(self, int_name, _int_param, _app_param):
        logging.info('on_check_interest(): {}'.format(Name.to_str(int_name)))

        response = None
        process_id = None
        try:
            parameter = self.decode_cmd_param_bytes(int_name)
            process_id = parameter.process_id
            if process_id == None:
                raise DecodeError()
        except (DecodeError, IndexError, RuntimeError) as exc:
            response = RepoCommandResponse()
            response.status_code = 403
            logging.warning('Command blob decoding failed')
        if response is None and process_id not in self.m_processes:
            response = RepoCommandResponse()
            response.status_code = 404
            logging.warning('Process does not exist')

        if response is None:
            self.reply_with_response(int_name, self.m_processes[process_id])
        else:
            self.reply_with_response(int_name, response)

    def reply_with_status(self, int_name: Name, status_code: int):
        ret = RepoCommandResponse()
        ret.status_code = status_code
        self.reply_with_response(int_name, ret)

    def reply_with_response(self, int_name, response: RepoCommandResponse):
        logging.info('Reply to command: {}'.format(Name.to_str(int_name)))
        response_bytes = response.encode()
        self.app.put_data(int_name, response_bytes, freshness_period=1000)

    @staticmethod
    def decode_cmd_param_bytes(name) -> RepoCommandParameter:
        """
        Decode the command interest and return a RepoCommandParameter object.
        Command interests have the format of:
        /<routable_repo_prefix>/insert/<cmd_param_blob>/<timestamp>/<random-value>/<SignatureInfo>/<SignatureValue>
        Throw RuntimeError on decoding failure.
        """
        param_bytes = Component.get_value(name[-1])   # TODO: accept command interest instead of regular interests
        return RepoCommandParameter.parse(param_bytes)

    async def schedule_delete_process(self, process_id: int):
        """
        Remove process state after some delay
        TODO: Remove hard-coded duration
        """
        await asyncio.sleep(60)
        if process_id in self.m_processes:
            del self.m_processes[process_id]
