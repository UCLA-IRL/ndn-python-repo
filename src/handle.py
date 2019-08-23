import os
import asyncio
import json
import logging
import pickle
import random
import sys
from typing import Optional, Callable, Union
from pyndn import Blob, Face, Name, Data, Interest, NetworkNack
from pyndn.security import KeyChain
from pyndn.encoding import ProtobufTlv
from asyncndn import fetch_segmented_data, fetch_data_packet
from storage import Storage
from controller import Controller
from command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from command.repo_command_response_pb2 import RepoCommandResponseMessage
from command.repo_storage_format_pb2 import PrefixesInStorage, CommandsInStorage


class ReadHandle(object):
    def __init__(self, face: Face, keychain: KeyChain, storage: Storage):
        self.face = face
        self.keychain = keychain
        self.storage = storage

    def listen(self, name: Name):
        """
        This function needs to be called for prefix of all data stored.
        """
        self.face.registerPrefix(name, None,
                                 lambda prefix: logging.error('Prefix registration failed: %s', prefix))
        self.face.setInterestFilter(name, self.on_command)
        logging.info('Read handle: listening to {}'.format(str(name)))

    def on_command(self, _prefix, interest: Interest, face, _filter_id, _filter):
        name = interest.getName()

        if not self.storage.exists(str(name)):
            return

        raw_data = self.storage.get(str(name))
        data = Data()
        data.wireDecode(Blob(pickle.loads(raw_data)))
        self.face.putData(data)

        logging.info('Read handle: serve data {}'.format(interest.getName()))


class CommandHandle(object):
    """
    Command handle need to keep a reference to the read handle. This is required for prefix 
    registration after inserting new data.
    """
    def __init__(self, face: Face, keychain: KeyChain, storage: Storage, controller_prefix: Name,
                 read_handle: ReadHandle):
        self.face = face
        self.keychain = keychain
        self.storage = storage
        self.controller_prefix = controller_prefix
        self.read_handle = read_handle
        self.m_processes = dict()

        self.seq_to_cmd = {}    # int -> Interest
        self.exec_seq = 0       # Seq of last executed command

    def listen(self, name: Name):
        """
        Start listening for command interests. Also, listen for requests for commands, which is
        required for command synchronization across multiple repos.
        This function needs to be called explicitly after initialization.
        """
        self.face.setInterestFilter(Name(name).append('insert'), self.on_command)
        logging.info('Set interest filter: {}'.format(Name(name).append('insert')))
        
        # TODO: listen to delete

    def on_command(self, _prefix, interest: Interest, face, _filter_id, _filter):
        # TODO: Add segmented interest processing
        event_loop = asyncio.get_event_loop()
        event_loop.create_task(self.process_cmd(interest))

    def reply_to_cmd(self, interest: Interest, response: RepoCommandResponseMessage):
        """
        Reply to a command interest
        """
        logging.info('Reply to command: {}'.format(interest.getName()))

        response_blob = ProtobufTlv.encode(response)
        data = Data(interest.getName())
        data.metaInfo.freshnessPeriod = 1000
        data.setContent(response_blob)

        self.keychain.sign(data)
        self.face.putData(data)
    
    async def process_cmd(self, interest: Interest):
        """
        Verify and execute command in sequence.
        The commands must be executed in sequence to guarantee consistency. Commands with larger
        sequence number have to wait for smaller commands.
        """
        cmd_seq = await self.verify_cmd(interest)
        if cmd_seq is None:
            return
        self.seq_to_cmd[cmd_seq] = interest
        self.update_commands_in_storage(interest, cmd_seq)

        event_loop = asyncio.get_event_loop()
        while self.exec_seq + 1 in self.seq_to_cmd:
            cmd_type = self.seq_to_cmd[self.exec_seq + 1].getName().toUri().split('/')[-6]
            if cmd_type == 'insert':
                event_loop.create_task(self.process_segmented_insert_command(interest))
            elif cmd_type == 'delete':
                event_loop.create_task(self.process_delete_command(interest))
            else:
                log.fatal('Unrecognized command')
            self.exec_seq += 1
            self.update_exec_seq_in_storage(self.exec_seq)

    async def verify_cmd(self, interest: Interest) -> Optional[int]:
        """
        Verify command authenticity with the remote controller. If verified, return the seq number 
        assigned by the controller.
        """
        verify_interest = Interest(Name(self.controller_prefix).append('verify')
                                   .append(interest.getName()))
        verify_interest.applicationParameters = interest.applicationParameters
        verify_interest.appendParametersDigestToName()
        
        response = await fetch_data_packet(self.face, verify_interest)

        response = json.loads(response.content.toBytes().decode("utf-8"))
        return response['seq'] if response['valid'] else None
    
    async def process_segmented_insert_command(self, interest: Interest):
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

        parameter = self.decode_cmd_param_blob(interest)
        start_block_id = parameter.repo_command_parameter.start_block_id
        end_block_id = parameter.repo_command_parameter.end_block_id
        name = Name()
        for compo in parameter.repo_command_parameter.name.component:
            name.append(compo)

        logging.info("Write handle processing segmented interest: {}, {}, {}"
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

        existing = self.update_prefixes_in_storage(name.toUri())
        if existing is False:
            self.read_handle.listen(name)

        if process_id in self.m_processes:
            await self.delete_process(process_id)

    async def delete_process(self, process_id: int):
        """
        Remove process state after some delay
        TODO: Remove hard-coded duration
        """
        await asyncio.sleep(10)
        if process_id in self.m_processes:
            del self.m_processes[process_id]

    def process_delete_command(self, interest: Interest):
        """
        Process delete command.
        Return to client with status code 100 immediately, and then start data fetching process.
        TODO
        """
    
    def update_prefixes_in_storage(self, prefix: str) -> bool:
        """
        Add a new prefix into database
        Return whether the prefix has been registered before
        """
        prefixes_msg = PrefixesInStorage()
        ret = self.storage.get('prefixes')
        if ret:
            prefixes_msg.ParseFromString(ret)
        for prefix_item in prefixes_msg.prefixes:
            if prefix_item.name == prefix or prefix.startswith(prefix_item.name):
                return True
        new_prefix = prefixes_msg.prefixes.add()
        new_prefix.name = prefix
        self.storage.put("prefixes", prefixes_msg.SerializeToString())
        logging.info("added a new prefix into the database")
        return False
    
    def update_commands_in_storage(self, interest: Interest, seq: int) -> bool:
        """
        Add a new command and its seq into database
        Return whether the command has been inserted before
        """
        command_msg = CommandsInStorage()
        ret = self.storage.get('commands')
        if ret:
            command_msg.ParseFromString(ret)
        for command_item in command_msg.commands:
            if command_item.seq == seq:
                return True
        new_command = command_msg.commands.add()
        new_command.interest = interest.wireEncode().toBytes()
        new_command.seq = seq
        self.storage.put('commands', command_msg.SerializeToString())
        logging.info('added a new command into the database, seq = {}'.format(seq))
        return False
    
    def update_exec_seq_in_storage(self, exec_seq: int):
        """
        Update execution sequence in storage
        """
        self.storage.put('exec_seq', (exec_seq).to_bytes(2, byteorder='little'))

    @staticmethod
    def decode_cmd_param_blob(interest: Interest):
        """
        Decode the command interest and return a RepoCommandParameterMessage object.
        Command interests have the format of:
        /<routable_repo_prefix>/insert/<cmd_param_blob>/<timestamp>/<random-value>/<SignatureInfo>/<SignatureValue>
        """
        parameter = RepoCommandParameterMessage()
        param_blob = interest.getName()[-5].getValue()

        try:
            ProtobufTlv.decode(parameter, param_blob)
        except RuntimeError as exc:
            print('Decode failed', exc)
        return parameter

