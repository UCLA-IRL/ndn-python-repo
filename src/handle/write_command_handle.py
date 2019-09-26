import asyncio
import logging
import pickle
import random
from typing import Optional, Callable, Union
from pyndn import Blob, Face, Name, Data, Interest, NetworkNack
from pyndn.security import KeyChain
from pyndn.encoding import ProtobufTlv
from . import ReadHandle, CommandHandle
from src.asyncndn import fetch_segmented_data
from src.storage import Storage
from src.command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from src.command.repo_command_response_pb2 import RepoCommandResponseMessage
from src.command.repo_storage_format_pb2 import PrefixesInStorage


class WriteCommandHandle(CommandHandle):
    """
    WriteHandle processes command interests, and fetches corresponding data to
    store them into the database.
    TODO: Add validator
    """
    def __init__(self, face: Face, keychain: KeyChain, storage: Storage,
                 read_handle: ReadHandle):
        """
        Write handle need to keep a reference to write handle to register new prefixes.
        """
        super(WriteCommandHandle, self).__init__(face, keychain, storage)
        self.m_processes = dict()
        self.m_read_handle = read_handle

    def listen(self, name: Name):
        """
        Start listening for command interests.
        This function needs to be called explicitly after initialization.
        """
        self.face.setInterestFilter(Name(name).append('insert'), self.on_insert_interest)
        logging.info('Set interest filter: {}'.format(Name(name).append('insert')))
        self.face.setInterestFilter(Name(name).append('insert check'), self.on_check_interest)
        logging.info('Set interest filter: {}'.format(Name(name).append('insert check')))

    def on_insert_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        event_loop = asyncio.get_event_loop()
        event_loop.create_task(self.process_insert(interest))

    async def process_insert(self, interest: Interest):
        """
        Process segmented insertion command.
        Return to client with status code 100 immediately, and then start data fetching process.
        TODO: When to start listening for interest
        """
        def after_fetched(data: Union[Data, NetworkNack, None]):
            nonlocal n_success, n_fail
            # If success, save to storage
            if isinstance(data, Data):
                n_success += 1
                self.storage.put(str(data.getName()), pickle.dumps(data.wireEncode().toBytes()))
                logging.info('Inserted data: {}'.format(data.getName()))
            else:
                n_fail += 1
        
        try:
            parameter = self.decode_cmd_param_blob(interest)
        except RuntimeError as exc:
            return

        start_block_id = parameter.repo_command_parameter.start_block_id
        end_block_id = parameter.repo_command_parameter.end_block_id
        name = Name()
        for compo in parameter.repo_command_parameter.name.component:
            name.append(compo)

        logging.info('Write handle processing segmented interest: {}, {}, {}'
                     .format(name, start_block_id, end_block_id))

        # Reply to client with status code 100
        process_id = random.randint(0, 0x7fffffff)
        self.m_processes[process_id] = RepoCommandResponseMessage()
        self.m_processes[process_id].repo_command_response.status_code = 100
        self.m_processes[process_id].repo_command_response.process_id = process_id
        self.m_processes[process_id].repo_command_response.insert_num = 0

        self.reply_to_cmd(interest, self.m_processes[process_id])

        # Start data fetching process. This semaphore size should be smaller
        # than the number of attempts before failure
        self.m_processes[process_id].repo_command_response.status_code = 300
        semaphore = asyncio.Semaphore(2)
        n_success = 0
        n_fail = 0

        await fetch_segmented_data(self.face, name, start_block_id, end_block_id,
                                   semaphore, after_fetched)

        # If both start_block_id and end_block_id are specified, check if all data have being fetched
        if end_block_id is None or n_success == (end_block_id - (start_block_id if start_block_id else 0) + 1):
            self.m_processes[process_id].repo_command_response.status_code = 200
            logging.fatal('Segment insertion success, {} items inserted'.format(n_success))
        else:
            self.m_processes[process_id].repo_command_response.status_code = 400
            logging.info('Segment insertion failure, {} items inserted'.format(n_success))
        self.m_processes[process_id].repo_command_response.insert_num = 1

        existing = CommandHandle.update_prefixes_in_storage(self.storage, name.toUri())
        if not existing:
            self.m_read_handle.listen(name)

        if process_id in self.m_processes:
            await self.delete_process(process_id)
    
    def on_check_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        logging.info('on_check_interest(): {}'.format(str(interest.getName())))
        response = None
        try:
            parameter = self.decode_cmd_param_blob(interest)
        except RuntimeError as exc:
            response = RepoCommandResponseMessage()
            response.status_code = 403
        process_id = parameter.repo_command_parameter.process_id

        if process_id not in self.m_processes:
            response = RepoCommandResponseMessage()
            response.repo_command_response.status_code = 404
        
        if response is not None:
            self.reply_to_cmd(interest, response)
        else:
            self.reply_to_cmd(interest, self.m_processes[process_id])
            

    async def delete_process(self, process_id: int):
        """
        Remove process state after some delay
        TODO: Remove hard-coded duration
        """
        await asyncio.sleep(60)
        if process_id in self.m_processes:
            del self.m_processes[process_id]