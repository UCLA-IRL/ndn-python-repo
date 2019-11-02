import asyncio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, Component

from src.storage import Storage
from src.command.repo_storage_format_pb2 import PrefixesInStorage
from src.command.repo_commands import RepoCommandParameter, RepoCommandResponse


class CommandHandle(object):
    """
    Interface for command interest handles
    """
    def __init__(self, app: NDNApp, storage: Storage):
        self.app = app
        self.storage = storage
        self.m_processes = dict()

    def listen(self, name: Name):
        raise NotImplementedError

    def on_check_interest(self, int_name, _int_param, _app_param):
        logging.info('on_check_interest(): {}'.format(Name.to_str(int_name)))

        response = None
        process_id = None
        try:
            parameter = self.decode_cmd_param_blob(int_name)
            process_id = parameter.process_id
        except RuntimeError as exc:
            response = RepoCommandResponse()
            response.status_code = 403
        if response is None and process_id not in self.m_processes:
            response = RepoCommandResponse()
            response.status_code = 404

        if response is None:
            self.reply_to_cmd(int_name, self.m_processes[process_id])
        else:
            self.reply_to_cmd(int_name, response)

    @staticmethod
    def update_prefixes_in_storage(storage: Storage, prefix: str) -> bool:
        """
        Add a new prefix into database
        return whether the prefix has been registered before
        """
        prefixes_msg = PrefixesInStorage()
        ret = storage.get("prefixes")
        if ret:
            prefixes_msg.ParseFromString(ret)
        for prefix_item in prefixes_msg.prefixes:
            if prefix_item.name == prefix or prefix.startswith(prefix_item.name):
                return True
        new_prefix = prefixes_msg.prefixes.add()
        new_prefix.name = prefix
        storage.put("prefixes", prefixes_msg.SerializeToString())
        logging.info("add a new prefix into the database")
        return False

    def reply_to_cmd(self, int_name, response: RepoCommandResponse):
        """
        Reply to a command interest
        """
        logging.info('Reply to command: {}'.format(Name.to_str(int_name)))
        response_bytes = response.encode()
        self.app.put_data(int_name, response_bytes)

    @staticmethod
    def decode_cmd_param_blob(name) -> RepoCommandParameter:
        """
        Decode the command interest and return a RepoCommandParameterMessage object.
        Command interests have the format of:
        /<routable_repo_prefix>/insert/<cmd_param_blob>/<timestamp>/<random-value>/<SignatureInfo>/<SignatureValue>
        Throw RuntimeError on decoding failure.
        """
        param_blob = Component.get_value(name[-1])   # TODO: accept command interest instead of regular interests
        return RepoCommandParameter.parse(param_blob)

    async def schedule_delete_process(self, process_id: int):
        """
        Remove process state after some delay
        TODO: Remove hard-coded duration
        """
        await asyncio.sleep(60)
        if process_id in self.m_processes:
            del self.m_processes[process_id]