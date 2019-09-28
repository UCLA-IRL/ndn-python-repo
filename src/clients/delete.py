"""
    NDN Repo delete client.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-09-26
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
from command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from command.repo_command_response_pb2 import RepoCommandResponseMessage
from command_checker import CommandChecker


class DeleteClient(object):

    def __init__(self, face: Face, keychain: KeyChain):
        self.face = face
        self.keychain = keychain

    async def run(self, repo_name: str, prefix: str, start_block_id: int, end_block_id: int):
        """
        Send a delete command to remove all the data within [start_block_id, end_block_id].
        """
        # Send command interest
        prefix = Name(prefix)
        parameter = RepoCommandParameterMessage()
        for compo in prefix:
            parameter.repo_command_parameter.name.component.append(compo.getValue().toBytes())
        parameter.repo_command_parameter.start_block_id = start_block_id
        parameter.repo_command_parameter.end_block_id = end_block_id
        param_blob = ProtobufTlv.encode(parameter)

        name = Name(repo_name).append('delete').append(Name.Component(param_blob))
        interest = Interest(name)
        self.face.makeCommandInterest(interest)

        logging.info('Send delete command interest')
        ret = await fetch_data_packet(self.face, interest)

        # Parse response
        if not isinstance(ret, Data):
            logging.warning('Delete error')
            return
        response = RepoCommandResponseMessage()
        try:
            ProtobufTlv.decode(response, ret.content)
        except RuntimeError as exc:
            logging.warning('Response decoding failed', exc)
        process_id = response.repo_command_response.process_id
        status_code = response.repo_command_response.status_code

        logging.info('Delete process {} accepted, status {}'.format(process_id, status_code))

        # Use delete check command to probe if delete process is completed
        checker = CommandChecker(self.face, self.keychain)
        while True:
            response = await checker.check_delete(repo_name, process_id)
            if response.repo_command_response.status_code == 300:
                await asyncio.sleep(1)
            elif response.repo_command_response.status_code == 200:
                logging.info('Delete process {} status: {}, delete_num: {}'
                             .format(process_id, 
                                     response.repo_command_response.status_code,
                                     response.repo_command_response.delete_num))
                break
            else:
                # Shouldn't get here
                assert(False)


def main():
    face = Face()
    keychain = KeyChain()
    face.setCommandSigningInfo(keychain, keychain.getDefaultCertificateName())

    async def face_loop():
        nonlocal face
        while True:
            face.processEvents()
            await asyncio.sleep(0.001)

    parser = argparse.ArgumentParser(description='putfile')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-p', '--prefix',
                        required=True, help='Prefix of data')
    parser.add_argument('-s', '--start_block_id',
                        required=True, help='Start Block ID')
    parser.add_argument('-e', '--end_block_id',
                        required=True, help='End Block ID')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    client = DeleteClient(face, keychain)
    event_loop = asyncio.get_event_loop()
    event_loop.create_task(face_loop())
    event_loop.run_until_complete(client.run(args.repo_name,
                                             args.prefix,
                                             int(args.start_block_id),
                                             int(args.end_block_id)))

if __name__ == '__main__':
    main()