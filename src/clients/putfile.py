"""
    NDN Repo putfile client.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-07-14
"""

import os, sys
import argparse
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import argparse
import asyncio
import logging
from pyndn import Blob, Face, Name, Data, Interest
from pyndn.security import KeyChain
from pyndn.encoding import ProtobufTlv
from asyncndn import fetch_data_packet
from command_checker import CommandChecker
from command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from command.repo_command_response_pb2 import RepoCommandResponseMessage

MAX_BYTES_IN_DATA_PACKET = 2000


class PutfileClient(object):
    """
    This client serves random segmented data
    """
    def __init__(self, args):
        self.repo_name = Name(args.repo_name)
        self.file_path = args.file_path
        self.name_at_repo = Name(args.name)

        self.face = Face()
        self.keychain = KeyChain()
        self.face.setCommandSigningInfo(self.keychain, self.keychain.getDefaultCertificateName())
        self.running = True
        self.m_name_str_to_data = dict()
        self.n_packets = 0

        self.prepare_data()
        self.face.registerPrefix(self.name_at_repo, None, self.on_register_failed)
        self.face.setInterestFilter(self.name_at_repo, self.on_interest)

    async def face_loop(self):
        while self.running:
            self.face.processEvents()
            await asyncio.sleep(0.001)

    def prepare_data(self):
        """
        Shard file into data packets.
        """
        logging.info('preparing data')
        with open(self.file_path, 'rb') as binary_file:
            b_array = bytearray(binary_file.read())

        if len(b_array) == 0:
            logging.warning("File is 0 bytes")
            return

        self.n_packets = int((len(b_array) - 1) / MAX_BYTES_IN_DATA_PACKET + 1)
        logging.info('There are {} packets in total'.format(self.n_packets))
        seq = 0
        for i in range(0, len(b_array), MAX_BYTES_IN_DATA_PACKET):
            data = Data(Name(self.name_at_repo).append(str(seq)))
            data.metaInfo.freshnessPeriod = 100000
            data.setContent(b_array[i : min(i + MAX_BYTES_IN_DATA_PACKET, len(b_array))])
            data.metaInfo.setFinalBlockId(Name.Component.fromSegment(self.n_packets - 1))
            self.keychain.signWithSha256(data)
            self.m_name_str_to_data[str(data.getName())] = data
            seq += 1

    @staticmethod
    def on_register_failed(prefix):
        logging.error("Prefix registration failed: %s", prefix)

    def on_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        logging.info('On interest: {}'.format(interest.getName()))

        if str(interest.getName()) in self.m_name_str_to_data:
            self.face.putData(self.m_name_str_to_data[str(interest.getName())])
            logging.info('Serve data: {}'.format(interest.getName()))
        else:
            logging.info('Data does not exist: {}'.format(interest.getName()))

    async def insert_segmented_file(self):
        event_loop = asyncio.get_event_loop()
        face_task = event_loop.create_task(self.face_loop())

        parameter = RepoCommandParameterMessage()
        for compo in self.name_at_repo:
            parameter.repo_command_parameter.name.component.append(compo.getValue().toBytes())
        parameter.repo_command_parameter.start_block_id = 0
        parameter.repo_command_parameter.end_block_id = self.n_packets - 1
        param_blob = ProtobufTlv.encode(parameter)

        # Prepare cmd interest
        name = Name(self.repo_name).append('insert').append(Name.Component(param_blob))
        interest = Interest(name)
        self.face.makeCommandInterest(interest)

        logging.info('Send insert command interest')
        ret = await fetch_data_packet(self.face, interest)

        if not isinstance(ret, Data):
            logging.warning('Insert failed')
            return

        response = RepoCommandResponseMessage()
        try:
            ProtobufTlv.decode(response, ret.content)
        except RuntimeError as exc:
            logging.warning('Response decoding failed', exc)
        process_id = response.repo_command_response.process_id
        status_code = response.repo_command_response.status_code
        logging.info('Insertion process {} accepted: status code {}'
                     .format(process_id, status_code))

        # Use insert check command to probe if insert process is completed
        checker = CommandChecker(self.face, self.keychain)
        while True:
            response = await checker.run(self.repo_name, process_id)
            if response is None or response.repo_command_response.status_code == 300:
                await asyncio.sleep(1)
            elif response.repo_command_response.status_code == 200:
                logging.info('Insert process {} status: {}, insert_num: {}'
                             .format(process_id, 
                                     response.repo_command_response.status_code,
                                     response.repo_command_response.insert_num))
                break
            else:
                # Shouldn't get here
                assert(False)
        self.running = False
        await face_task


def main():
    parser = argparse.ArgumentParser(description='putfile')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-f', '--file_path',
                        required=True, help='Path to input file')
    parser.add_argument('-n', '--name',
                        required=True, help='Name used to store file at Repo')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    client = PutfileClient(args)

    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(client.insert_segmented_file())
    finally:
        event_loop.close()


if __name__ == "__main__":
    main()

