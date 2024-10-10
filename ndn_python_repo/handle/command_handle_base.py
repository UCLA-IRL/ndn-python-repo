import asyncio as aio
import logging
import json
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName, FormalName, Component
from ndn.encoding.tlv_model import DecodeError

from ..command import RepoStatQuery, RepoCommandRes, RepoStatCode, RepeatedNames, RepoCommandParam
from ..storage import Storage
from ..utils import PubSub

from hashlib import sha256

class CommandHandle(object):
    """
    Interface for command interest handles
    """
    def __init__(self, app: NDNApp, storage: Storage, pb: PubSub, _config: dict):
        self.app = app
        self.storage = storage
        self.pb = pb
        self.m_processes = dict()
        self.logger = logging.getLogger(__name__)

    async def listen(self, prefix: Name):
        raise NotImplementedError

    def _on_check_interest(self, int_name, _int_param, app_param):
        self.logger.info('on_check_interest(): {}'.format(Name.to_str(int_name)))

        response = None
        request_no = None
        try:
            if not app_param:
                raise DecodeError('Missing Parameters')
            parameter = RepoStatQuery.parse(app_param)
            request_no = parameter.request_no
            if request_no is None:
                raise DecodeError('Missing Request No.')
        except (DecodeError, IndexError, RuntimeError) as exc:
            response = RepoCommandRes()
            response.status_code = RepoStatCode.MALFORMED
            self.logger.warning(f'Command blob decoding failed for exception {exc}')

        if response is None and request_no not in self.m_processes:
            response = RepoCommandRes()
            response.status_code = RepoStatCode.NOT_FOUND
            self.logger.warning(f'Process does not exist for id={request_no}')

        if response is None:
            self.reply_with_response(int_name, self.m_processes[request_no])
        else:
            self.reply_with_response(int_name, response)

    def reply_with_response(self, int_name, response: RepoCommandRes):
        self.logger.info(f'Reply to command: {Name.to_str(int_name)} w/ code={response.status_code}')
        response_bytes = response.encode()
        self.app.put_data(int_name, response_bytes, freshness_period=1000)

    async def _delete_process_state_after(self, process_id: bytes, delay: int):
        """
        Remove process state after some delay.
        """
        await aio.sleep(delay)
        if process_id in self.m_processes:
            del self.m_processes[process_id]

    def parse_msg(self, msg):
        try:
            cmd_param = RepoCommandParam.parse(msg)
            request_no = sha256(bytes(msg)).digest()
            if not cmd_param.objs:
                raise DecodeError('Missing objects')
            for obj in cmd_param.objs:
                if obj.name is None:
                    raise DecodeError('Missing name for one or more objects')
        except (DecodeError, IndexError) as exc:
            self.logger.warning(f'Parameter interest blob decoding failed w/ exception: {exc}')
            return

        return cmd_param, request_no

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
    def get_name_from_set_in_storage(set_name: str, storage: Storage) -> list[FormalName]:
        """
        Get all names from set ``set_name`` in the storage.
        :param set_name: str
        :param storage: Storage
        :return: A list of ``FormalName``
        """
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

    # this will overwrite
    @staticmethod
    def add_dict_in_storage(dict_name: str, storage: Storage, s_dict: dict) -> bool:
        ret = storage._get(dict_name.encode('utf-8'))
        dict_bytes = json.dumps(s_dict).encode('utf-8')
        storage._put(dict_name.encode('utf-8'), dict_bytes)
        return ret is not None

    @staticmethod
    def get_dict_in_storage(dict_name: str, storage: Storage) -> dict:
        res_bytes = storage._get(dict_name.encode('utf-8'))
        return json.loads(res_bytes.decode('utf-8'))

    @staticmethod
    def remove_dict_in_storage(dict_name: str, storage: Storage) -> bool:
        return storage._remove(dict_name.encode('utf-8'))

    # Wrapper for registered prefixes
    @staticmethod
    def add_registered_prefix_in_storage(storage: Storage, prefix):
        ret = CommandHandle.add_name_to_set_in_storage('prefixes', storage, prefix)
        if not ret:
            logging.getLogger(__name__).info(f'Added new registered prefix to storage: {Name.to_str(prefix)}')
        return ret

    @staticmethod
    def get_registered_prefix_in_storage(storage: Storage):
        return CommandHandle.get_name_from_set_in_storage('prefixes', storage)

    @staticmethod
    def remove_registered_prefix_in_storage(storage: Storage, prefix):
        ret = CommandHandle.remove_name_from_set_in_storage('prefixes', storage, prefix)
        if ret:
            logging.getLogger(__name__).info(f'Removed existing registered prefix from storage: {Name.to_str(prefix)}')
        return ret

    @staticmethod
    def add_sync_states_in_storage(storage: Storage, sync_group: FormalName, states: dict):
        store_key = [Component.from_str('sync_states')] + sync_group
        logging.info(f'Added new sync states to storage: {Name.to_str(sync_group)}')
        return CommandHandle.add_dict_in_storage(Name.to_str(store_key), storage, states)

    @staticmethod
    def get_sync_states_in_storage(storage: Storage, sync_group: FormalName):
        store_key = [Component.from_str('sync_states')] + sync_group
        return CommandHandle.get_dict_in_storage(Name.to_str(store_key), storage)

    @staticmethod
    def remove_sync_states_in_storage(storage: Storage, sync_group: FormalName):
        store_key = [Component.from_str('sync_states')] + sync_group
        logging.info(f'Removed new sync states to storage: {Name.to_str(sync_group)}')
        return CommandHandle.remove_dict_in_storage(Name.to_str(store_key), storage)
    
    @staticmethod
    def add_sync_group_in_storage(storage: Storage, sync_group: FormalName):
        ret = CommandHandle.add_name_to_set_in_storage('sync_groups', storage, sync_group)
        if not ret:
            logging.info(f'Added new sync group to storage: {Name.to_str(sync_group)}')
        return ret

    @staticmethod
    def get_sync_groups_in_storage(storage: Storage):
        return CommandHandle.get_name_from_set_in_storage('sync_groups', storage)

    @staticmethod
    def remove_sync_group_in_storage(storage: Storage, sync_group: FormalName):
        ret = CommandHandle.remove_name_from_set_in_storage('sync_groups', storage, sync_group)
        if ret:
            logging.info(f'Removed existing sync_group from storage: {Name.to_str(sync_group)}')
        return ret