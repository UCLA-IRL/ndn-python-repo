import os
import sys
import asyncio
import logging
from pyndn import Face, Name, Data, Interest
from pyndn.security import KeyChain
from pyndn.encoding import ProtobufTlv
from asyncndn import fetch_data_packet
from command.repo_command_parameter_pb2 import RepoCommandParameterMessage
from command.repo_command_response_pb2 import RepoCommandResponseMessage


class SegmentedInsertClient(object):
    """
    This client serves random segmented data
    """
    def __init__(self, prefix: Name):

        self.prefix = prefix
        self.face = Face()
        self.keychain = KeyChain()
        self.face.setCommandSigningInfo(self.keychain, self.keychain.getDefaultCertificateName())
        self.running = True
        self.serve_data()

        event_loop = asyncio.get_event_loop()
        event_loop.create_task(self.face_loop())

    async def face_loop(self):
        while self.running:
            self.face.processEvents()
            await asyncio.sleep(0.01)

    async def insert_segmented_data(self, repo_prefix: Name):
        event_loop = asyncio.get_event_loop()
        face_task = event_loop.create_task(self.face_loop())

        parameter = RepoCommandParameterMessage()
        for compo in self.prefix:
            parameter.repo_command_parameter.name.component.append(compo.getValue().toBytes())
        parameter.repo_command_parameter.start_block_id = 0
        parameter.repo_command_parameter.end_block_id = 10
        param_blob = ProtobufTlv.encode(parameter)

        # Prepare cmd interest
        name = repo_prefix
        name.append("insert").append(Name.Component(param_blob))
        interest = Interest(name)
        interest.canBePrefix = True
        self.face.makeCommandInterest(interest)

        logging.info("Express interest: {}".format(interest.getName()))
        ret = await fetch_data_packet(self.face, interest)

        if not isinstance(ret, Data):
            logging.warning("Insertion failed")
        else:
            # Parse response
            response = RepoCommandResponseMessage()
            try:
                ProtobufTlv.decode(response, ret.content)
                logging.info('Insertion command accepted: status code {}'
                             .format(response.repo_command_response.status_code))
            except RuntimeError as exc:
                logging.warning('Response decoding failed', exc)

        # Wait extra time for data to be served
        await asyncio.gather(face_task, asyncio.sleep(10))
        running = False

    def serve_data(self):
        logging.info('Serving data')
        self.face.registerPrefix(self.prefix, None, self.on_register_failed)
        self.face.setInterestFilter(self.prefix, self.on_interest)

    def on_interest(self, _prefix, interest: Interest, face, _filter_id, _filter):
        logging.info('On interest: {}'.format(interest.getName()))
        data = Data(interest.getName())
        data.setContent("foobar".encode('utf-8'))
        self.keychain.sign(data)
        self.face.putData(data)

    @staticmethod
    def on_register_failed(prefix):
        logging.error("Prefix registration failed: %s", prefix)


def main():
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    client = SegmentedInsertClient(Name('testdata'))
    event_loop = asyncio.get_event_loop()
    event_loop.create_task(client.insert_segmented_data(Name('testrepo')))
    try:
        event_loop.run_until_complete(client.face_loop())
    finally:
        event_loop.close()


if __name__ == "__main__":
    main()

