import os
import sys
import asyncio
import logging
from pyndn import Face, Name, Data, Interest
from pyndn.security import KeyChain
from pyndn.encoding import ProtobufTlv
from asyncndn import fetch_data_packet
from encoding.repo_command_parameter_pb2 import RepoCommandParameterMessage
from encoding.repo_command_response_pb2 import RepoCommandResponseMessage


class SingleInsertClient(object):
    def __init__(self):
        self.face = Face()
        self.keychain = KeyChain()
        self.face.setCommandSigningInfo(self.keychain, self.keychain.getDefaultCertificateName())

    async def insert_single_data(self, repo_prefix: Name, data_prefix: Name):
        face = self.face
        running = True

        async def face_loop():
            nonlocal face, running
            while running:
                face.processEvents()
                await asyncio.sleep(0.01)

        event_loop = asyncio.get_event_loop()
        face_task = event_loop.create_task(face_loop())

        parameter = RepoCommandParameterMessage()
        for compo in data_prefix:
            parameter.repo_command_parameter.name.component.append(compo.getValue().toBytes())
        param_blob = ProtobufTlv.encode(parameter)

        # Prepare cmd interest
        name = repo_prefix
        name.append("insert").append(Name.Component(param_blob))
        interest = Interest(name)
        interest.canBePrefix = True
        self.face.makeCommandInterest(interest)

        print("Express interest: {}".format(interest.getName()))
        ret = await fetch_data_packet(self.face, interest)

        if not isinstance(ret, Data):
            print("Insertion failed")
        else:
            # Parse response
            response = RepoCommandResponseMessage()
            try:
                ProtobufTlv.decode(response, ret.content)
                print('Insertion command succeeded: status code {}'.format(response.repo_command_response.status_code))
            except RuntimeError as exc:
                print('Response decoding failed', exc)

        running = False
        await face_task


def main():
    client = SingleInsertClient()
    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(client.insert_single_data(Name('testrepo'), Name('testdata')))
    finally:
        event_loop.close()


if __name__ == "__main__":
    main()

