import os
import sys
import logging
import asyncio
import random
import pickle
from typing import Union, Dict, List, Optional
from pyndn import Face, Name, Data, Interest
from pyndn.security import KeyChain
from pyndn.encoding import ProtobufTlv
from asyncndn import fetch_data_packet
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
        Start listening for command interests.
        This function needs to be called explicitly before being used.
        """
        pass


class CommandHandle(object):
    """
    Interface for command interest handles
    TODO: insertion check command
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
    """
    def __init__(self, face: Face, keychain: KeyChain, storage: Storage):
        super(WriteCommandHandle, self).__init__(face, keychain, storage)
        self.m_processes = dict()

    def listen(self, name: Name):
        """
        Start listening for command interests.
        This function needs to be called explicitly after initialization.
        """
        self.face.setInterestFilter(Name(name).append("insert"), self.on_interest)
        logging.info("Set interest filter: {}".format(Name(name).append("insert")))

    def on_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        """
        On receiving command interest for data insertion
        """
        # TODO: Add segmented interest procssing
        event_loop = asyncio.get_event_loop()
        event_loop.create_task(self.process_segmented_insert_command(interest))

    # async def process_single_insert_command(self, interest: Interest):
    #     """
    #     Process a single insertion command..
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
    #             self.storage.put(fetch_data.getName(), pickle.dumps(fetch_data))
    #             self.m_processes[process_id].repo_command_response.status_code = 200
    #             self.m_processes[process_id].repo_command_response.insert_num = 1
    #
    #             logging.info("Stored data: {}".format(fetch_data.getName()))
    #
    #             await self.delete_process(process_id)

    async def process_segmented_insert_command(self, interest: Interest):
        parameter = self.decode_cmd_param_blob(interest)
        name = parameter.repo_command_parameter.name
        start_block_id = parameter.repo_command_parameter.start_block_id
        end_block_id = parameter.repo_command_parameter.end_block_id

        logging.info("Write handle processing single interest: {}, {}, {}"
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

        n_inserted = await self.fetch_segmented_data(name, start_block_id, end_block_id, semaphore)

        if not end_block_id or n_inserted == (end_block_id - (start_block_id if start_block_id else 0) + 1):
            self.m_processes[process_id].repo_command_response.status_code = 200
            logging.info('Segment insertion success')
        else:
            self.m_processes[process_id].repo_command_response.status_code = 400
            logging.info('Segment insertion failure')
        self.m_processes[process_id].repo_command_response.insert_num = 1

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

    async def fetch_segmented_data(self, prefix: Name, start_block_id: Optional[int],
                                   end_block_id: Optional[int], semaphore: asyncio.Semaphore) -> int:
        """
        Fetch segmented data from start_block_id or 0, to end_block_id or FinalBlockId returned
        in data, whichever is smaller.
        Maintain a fixed size window using semaphore.
        Return number of inserted elements
        TODO: Remove hard-coded part
        TODO: When to stop if end_block_id doesn't exist?
        """
        FETCHER_RETRY_INTERVAL = 1
        FETCHER_MAX_ATTEMPT_NUMBER = 3

        async def retry_or_fail(interest):
            """
            Retry for up to FETCHER_MAX_ATTEMPT_NUMBER times, and write to storage
            """
            logging.info('fetch_or_fail(): {}'.format(interest.getName()))
            nonlocal n_inserted, n_requested, done, final_id
            success = False
            for _ in range(FETCHER_MAX_ATTEMPT_NUMBER):
                response = await fetch_data_packet(self.face, interest)
                if isinstance(response, Data):
                    success = True
                    break
                else:
                    await asyncio.sleep(FETCHER_RETRY_INTERVAL / 1000.0)
            semaphore.release()
            n_requested += 1

            # If success, save to storage
            if success:
                n_inserted += 1
                final_id_component = response.metaInfo.getFinalBlockId()
                if final_id_component.isSegment():
                    final_id = final_id_component.toSegment()
                if n_requested >= final_id - start_block_id:
                    done.set()

                logging.info('Writing to storage: {}'.format(response.getName()))
                self.storage.put(response.getName(), pickle.dumps(response))

        cur_id = (start_block_id if start_block_id else 0)
        final_id = (end_block_id if end_block_id else 0x7fffffff)
        n_requested = 0
        n_inserted = 0
        event_loop = asyncio.get_event_loop()
        done = asyncio.Event()

        # Need to acquire semaphore before adding task to event loop, otherwise an unlimited
        # number of tasks would be added
        while cur_id <= final_id:
            await semaphore.acquire()
            interest = Interest(Name(prefix).appendSegment(cur_id))
            event_loop.create_task(retry_or_fail(interest))
            cur_id += 1
        await done.wait()

        return n_inserted


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
        """
        On receiving command interest for data deletion
        """
        pass

