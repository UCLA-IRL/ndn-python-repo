"""
    NDN Repo getfile client.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-07-14
"""

import os, sys
import argparse
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import asyncio
import logging
from pyndn import Blob, Face, Name, Data, Interest
from pyndn.security import KeyChain
from asyncndn import fetch_segmented_data


class GetfileClient(object):

    def __init__(self, args):
        """
        This client fetches a file from the repo, and save it to working directory.
        """
        self.repo_name = Name(args.repo_name)
        self.name_at_repo = Name(args.name)

        self.face = Face()
        self.keychain = KeyChain()
        self.face.setCommandSigningInfo(self.keychain, self.keychain.getDefaultCertificateName())
        self.running = True

    async def face_loop(self):
        while self.running:
            self.face.processEvents()
            await asyncio.sleep(0.001)

    async def fetch_segmented_file(self):
        """
        Fetch segmented data packets from the repo. Because the client doesn't know how the file
        is sharded, need to keep trying new block ids until no data is returned.
        """
        def after_fetched(data: Data):
            nonlocal recv_window, b_array, seq_to_bytes_unordered
            """
            Reassemble data packets in sequence.
            """
            if not isinstance(data, Data):
                return
            try:
                seq = int(str(data.getName()).split('/')[-1])
                logging.info('seq: {}'.format(seq))
            except ValueError:
                logging.warning('Sequence number decoding error')
                return

            # Temporarily store out-of-order packets
            if seq <= recv_window:
                return
            elif seq == recv_window + 1:
                b_array.extend(data.getContent().toBytes())
                logging.info('saved packet: seq {}'.format(seq))
                recv_window += 1
                while recv_window + 1 in seq_to_bytes_unordered:
                    b_array.extend(seq_to_bytes_unordered[recv_window + 1])
                    seq_to_bytes_unordered.pop(recv_window + 1)
                    logging.info('saved packet: seq {}'.format(recv_window + 1))
                    recv_window += 1
            else:
                logging.info('Received out of order packet: seq {}'.format(seq))
                seq_to_bytes_unordered[seq] = data.getContent().toBytes()

        event_loop = asyncio.get_event_loop()
        face_task = event_loop.create_task(self.face_loop())

        recv_window = -1
        b_array = bytearray()
        seq_to_bytes_unordered = dict()     # Temporarily save out-of-order packets

        semaphore = asyncio.Semaphore(100)
        await fetch_segmented_data(self.face, self.name_at_repo,
                                   start_block_id=0, end_block_id=None,
                                   semaphore=semaphore, after_fetched=after_fetched)

        if len(b_array) > 0:
            logging.info('Fetching completed, writing file to disk')
            with open(str(self.name_at_repo[-1]), 'wb') as f:
                f.write(b_array)

        self.running = False
        await face_task


def main():
    parser = argparse.ArgumentParser(description='segmented insert client')
    parser.add_argument('-r', '--repo_name',
                        required=True, help='Name of repo')
    parser.add_argument('-n', '--name',
                        required=True, help='Name used to store file at Repo')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    client = GetfileClient(args)

    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(client.fetch_segmented_file())
    finally:
        event_loop.close()


if __name__ == "__main__":
    main()

