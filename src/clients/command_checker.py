"""
    NDN Repo insert check tester.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-09-23
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


class CommandChecker(object):
    """
    Client for sending insert check interests.
    Users can create an CommandChecker instance to check for the status code.
    """
    def __init__(self, face: Face, keychain: KeyChain):
        self.face = face
        self.keychain = keychain
    
    async def check_insert(self, repo_name: str, process_id: int) -> RepoCommandResponseMessage:
        return await self._check('insert', repo_name, process_id)
    
    async def check_delete(self, repo_name: str, process_id: int) -> RepoCommandResponseMessage:
        return await self._check('delete', repo_name, process_id)

    async def _check(self, method: str, repo_name: str, process_id: int) -> RepoCommandResponseMessage:
        """
        Return parsed insert check response message.
        """
        parameter = RepoCommandParameterMessage()
        parameter.repo_command_parameter.process_id = process_id
        param_blob = ProtobufTlv.encode(parameter)

        name = Name(repo_name).append(method + ' check').append(Name.Component(param_blob))
        interest = Interest(name)
        interest.canBePrefix = True
        interest.setInterestLifetimeMilliseconds(1000)
        self.face.makeCommandInterest(interest)

        logging.info('Send' + method + 'check interest')
        ret = await fetch_data_packet(self.face, interest)

        if not isinstance(ret, Data):
            logging.warning('Check error')
            return None
        try:
            response = self.decode_cmd_response_blob(ret)
        except RuntimeError as exc:
            logging.warning('Response blob decoding failed')
            return None
        return response

    @staticmethod
    def decode_cmd_response_blob(data: Data) -> RepoCommandResponseMessage:
        """
        Decode the command response and return a RepoCommandResponseMessage object.
        Throw RuntimeError on decoding failure.
        """
        response = RepoCommandResponseMessage()
        response_blob = data.getContent()
        try:
            ProtobufTlv.decode(response, response_blob)
        except RuntimeError as exc:
            raise exc
        return response

def main():
    face = Face()
    keychain = KeyChain()
    face.setCommandSigningInfo(keychain, keychain.getDefaultCertificateName())

    async def face_loop():
        nonlocal face
        while True:
            face.processEvents()
            await asyncio.sleep(0.001)

    parser = argparse.ArgumentParser(description='segmented insert client')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-p', '--process_id',
                        required=True, help="Process ID")
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    client = CommandChecker(face, keychain)
    event_loop = asyncio.get_event_loop()
    event_loop.create_task(face_loop())
    event_loop.run_until_complete(client.check_delete(args.repo_name, int(args.process_id)))


if __name__ == '__main__':
    main()