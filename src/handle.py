import os
import sys
import logging
import asyncio
import random
import pickle
from typing import Optional, Callable, Union
from pyndn import Blob, Face, Name, Data, Interest, NetworkNack
from pyndn.security import KeyChain
from pyndn.encoding import ProtobufTlv
from asyncndn import fetch_segmented_data
from storage import Storage
from command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from command.repo_command_response_pb2 import RepoCommandResponseMessage


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
                                 lambda prefix: logging.error("Prefix registration failed: %s", prefix))
        self.face.setInterestFilter(name, self.on_interest)
        logging.info('Read handle: listening to {}'.format(str(name)))

    def on_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
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
    Interface for command interest handles
    TODO: implement insertion check command
    """
    def __init__(self, face: Face, keychain: KeyChain, storage: Storage):
        self.face = face
        self.keychain = keychain
        self.storage = storage

    def listen(self, name: Name):
        raise NotImplementedError

    def on_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        raise NotImplementedError

    def reply_to_cmd(self, interest: Interest, response: RepoCommandResponseMessage):
        """
        Reply to a command interest
        """
        logging.info('Reply to command: {}'.format(interest.getName()))

        response_blob = ProtobufTlv.encode(response)
        data = Data(interest.getName())
        data.setContent(response_blob)

        self.keychain.sign(data)
        self.face.putData(data)

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


class WriteCommandHandle(CommandHandle):
    """
    WriteHandle processes command interests, and fetches corresponding data to
    store them into the database.
    TODO: Add validator
    TODO: Register interest for read handler
    """
    def __init__(self, face: Face, keychain: KeyChain, storage: Storage,
                 read_handle: ReadHandle):
        """
        Write handle need to keep a reference to write handle to register new prefixes
        """
        super(WriteCommandHandle, self).__init__(face, keychain, storage)
        self.m_processes = dict()
        self.m_read_handle = read_handle

    def listen(self, name: Name):
        """
        Start listening for command interests.
        This function needs to be called explicitly after initialization.
        """
        self.face.setInterestFilter(Name(name).append("insert"), self.on_interest)
        logging.info("Set interest filter: {}".format(Name(name).append("insert")))

    def on_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        # TODO: Add segmented interest processing
        event_loop = asyncio.get_event_loop()
        event_loop.create_task(self.process_segmented_insert_command(interest))

    # async def process_single_insert_command(self, interest: Interest):
    #     """
    #     Process a single insertion command.
    #     Return to client with status code 100 immediately, and then start data fetching process.
    #     TODO: Command verification and authentication
    #     TODO: Remove hard-coded part
    #     """
    #     parameter = self.decode_cmd_param_blob(interest)
    #
    #     logging.info("Write handle processing single interest: {}, {}, {}"
    #                  .format(parameter.repo_command_parameter.name,
    #                          parameter.repo_command_parameter.start_block_id,
    #                          parameter.repo_command_parameter.end_block_id))
    #
    #     # Reply to client with status code 100
    #     process_id = random.randint(0, 0x7fffffff)
    #     self.m_processes[process_id] = RepoCommandResponseMessage()
    #     self.m_processes[process_id].repo_command_response.status_code = 100
    #     self.m_processes[process_id].repo_command_response.process_id = process_id
    #     self.m_processes[process_id].repo_command_response.insert_num = 0
    #
    #     self.reply_to_cmd(interest, self.m_processes[process_id])
    #
    #     # Start data fetching process
    #     self.m_processes[process_id].repo_command_response.status_code = 300
    #     fetch_interest = Interest()
    #     for compo in parameter.repo_command_parameter.name.component:
    #         fetch_interest.name.append(compo)
    #     fetch_interest.setInterestLifetimeMilliseconds(4000)
    #
    #     fetch_data = await fetch_data_packet(self.face, interest)
    #
    #     if process_id in self.m_processes:
    #         if self.m_processes[process_id].repo_command_response.insert_num == 0:
    #             self.m_processes[process_id].repo_command_response.status_code = 200
    #             self.m_processes[process_id].repo_command_response.insert_num = 1
    #
    #             self.storage.put(fetch_data.getName(), pickle.dumps(fetch_data))
    #             logging.info("Inserted data: {}".format(fetch_data.getName()))
    #
    #             await self.delete_process(process_id)

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

        # Start data fetching process
        self.m_processes[process_id].repo_command_response.status_code = 300
        semaphore = asyncio.Semaphore(7)
        n_success = 0
        n_fail = 0

        await fetch_segmented_data(self.face, name, start_block_id, end_block_id,
                                   semaphore, after_fetched)

        # If both start_block_id and end_block_id are specified, check if all data have being fetched
        if not end_block_id or n_success == (end_block_id - (start_block_id if start_block_id else 0) + 1):
            self.m_processes[process_id].repo_command_response.status_code = 200
            logging.info('Segment insertion success, {} items inserted'.format(n_success))
        else:
            self.m_processes[process_id].repo_command_response.status_code = 400
            logging.info('Segment insertion failure, {} items inserted'.format(n_success))
        self.m_processes[process_id].repo_command_response.insert_num = 1

        if process_id in self.m_processes:
            await self.delete_process(process_id)

        self.m_read_handle.listen(name)

    async def delete_process(self, process_id: int):
        """
        Remove process state after some delay
        TODO: Remove hard-coded duration
        """
        await asyncio.sleep(10)
        if process_id in self.m_processes:
            del self.m_processes[process_id]


class DeleteCommandHandle(CommandHandle):
    """
    TODO: add validator
    """
    def listen(self, name: Name):
        """
        Start listening for command interests.
        This function needs to be called explicitly after initialization.
        """
        self.face.setInterestFilter(Name(name).append("delete"), self.on_interest)

    def on_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        event_loop = asyncio.get_event_loop()
        event_loop.create_task(self.process_segmented_insert_command(interest))

    def process_segmented_insert_command(self, interest: Interest):
        """
        Process segmented insertion command.
        Return to client with status code 100 immediately, and then start data fetching process.
        TODO
        """

