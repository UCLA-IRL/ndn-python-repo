import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, Component, NonStrictName, FormalName
from ndn.encoding.tlv_model import DecodeError
from typing import List

from ..command.repo_commands import RepoCommandParameter, RepoCommandResponse, RepeatedNames
from ..storage import Storage
from ..utils import PubSub


class CommandHandle(object):
    """
    Interface for command interest handles
    """
    def __init__(self, app: NDNApp, storage: Storage, pb: PubSub, config: dict):
        self.app = app
        self.storage = storage
        self.pb = pb
        self.m_processes = dict()

    async def listen(self, prefix: Name):
        raise NotImplementedError

    def _on_check_interest(self, int_name, _int_param, _app_param):
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
        param_bytes = Component.get_value(name[-1])
        return RepoCommandParameter.parse(param_bytes)

    async def _delete_process_state_after(self, process_id: bytes, delay: int):
        """
        Remove process state after some delay.
        """
        await aio.sleep(delay)
        if process_id in self.m_processes:
            del self.m_processes[process_id]

    @staticmethod
    def add_name_to_set_in_storage(set_name: str, storage: Storage, name: NonStrictName) -> bool:
        """
        Add ``name`` to set ``set_name`` in the storage. This function implements a set of Names\
            over the key-value storage interface. The set name is stored as the key, and the set\
            elements are serialized and stored as the value.
        :param set_name: str
        :param storage: Storage
        :param name: NonStrictName
        :return: Returns true if ``name`` is already in set ``set_name``. 
        """
        names_msg = RepeatedNames()
        ret = storage._get(set_name.encode('utf-8'))
        if ret:
            names_msg = RepeatedNames.parse(ret)

        name = Name.normalize(name)
        if name in names_msg.names:
            return True
        else:
            names_msg.names.append(name)
            names_msg_bytes = names_msg.encode()
            storage._put(set_name.encode('utf-8'), bytes(names_msg_bytes))
            return False
    
    @staticmethod
    def get_name_from_set_in_storage(set_name: str, storage: Storage) -> List[FormalName]:
        """
        Get all names from set ``set_name`` in the storage.
        :param set_name: str
        :param storage: Storage
        :return: A list of ``FormalName``
        """
        names_msg = RepeatedNames()
        ret = storage._get(set_name.encode('utf-8'))
        if ret:
            names_msg = RepeatedNames.parse(ret)
            return names_msg.names
        else:
            return []
    
    @staticmethod
    def remove_name_from_set_in_storage(set_name: str, storage: Storage, name: NonStrictName) -> bool:
        """
        Remove ``name`` from set ``set_name`` in the storage.
        :param set_name: str
        :param storage: Storage
        :param name: NonStrictName
        :return: Returns true if ``name`` exists in set ``set_name`` and is being successfully\
            removed.
        """
        names_msg = RepeatedNames()
        ret = storage._get(set_name.encode('utf-8'))
        if ret:
            names_msg = RepeatedNames.parse(ret)
        
        name = Name.normalize(name)
        if name in names_msg.names:
            names_msg.names.remove(Name.normalize(name))
            names_msg_bytes = names_msg.encode()
            storage._put(set_name.encode('utf-8'), bytes(names_msg_bytes))
            return True
        else:
            return False

    # Wrapper for registered prefixes
    @staticmethod
    def add_registered_prefix_in_storage(storage: Storage, prefix):
        ret = CommandHandle.add_name_to_set_in_storage('prefixes', storage, prefix)
        if not ret:
            logging.info(f'Added new registered prefix to storage: {Name.to_str(prefix)}')
        return ret

    @staticmethod
    def get_registered_prefix_in_storage(storage: Storage):
        return CommandHandle.get_name_from_set_in_storage('prefixes', storage)

    @staticmethod
    def remove_registered_prefix_in_storage(storage: Storage, prefix):
        ret = CommandHandle.remove_name_from_set_in_storage('prefixes', storage, prefix)
        if ret:
            logging.info(f'Removed existing registered prefix from storage: {Name.to_str(prefix)}')
        return ret

    # Wrapper for inserted filenames
    @staticmethod
    def add_inserted_filename_in_storage(storage: Storage, name):
        ret = CommandHandle.add_name_to_set_in_storage('inserted_filenames', storage, name)
        if ret:
            logging.info(f'Added new inserted filename to storage: {Name.to_str(name)}')
        return ret

    @staticmethod
    def get_inserted_filename_in_storage(storage: Storage):
        return CommandHandle.get_name_from_set_in_storage('inserted_filenames', storage)

    @staticmethod
    def remove_inserted_filename_in_storage(storage: Storage, name):
        ret = CommandHandle.remove_name_from_set_in_storage('inserted_filenames', storage, name)
        if ret:
            logging.info(f'Removed existing inserted filename from storage: {Name.to_str(name)}')
        return ret
