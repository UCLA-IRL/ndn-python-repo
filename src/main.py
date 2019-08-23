import asyncio
import logging
from pyndn import Face, Name
from pyndn.security import KeyChain
from repo import Repo
from handle import ReadHandle, CommandHandle
from storage import MongoDBStorage, LevelDBStorage
from config import get_yaml
from controller import Controller

# import cProfile, pstats, io
# from pstats import SortKey
# pr = cProfile.Profile()
# pr.enable()

def main():

    async def face_loop():
        nonlocal face, repo
        while repo.running:
            face.processEvents()
            await asyncio.sleep(0.001)

    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    config = get_yaml()
    print(config)

    face = Face()
    keychain = KeyChain()
    face.setCommandSigningInfo(keychain, keychain.getDefaultCertificateName())
    # storage = MongoDBStorage(config['db_config']['mongodb']['db'],
    #                          config['db_config']['mongodb']['collection'])
    storage = LevelDBStorage(config['db_config']['leveldb']['dir'])
    controller_prefix = config['controller']['prefix']

    read_handle = ReadHandle(face, keychain, storage)
    cmd_handle = CommandHandle(face, keychain, storage, Name(controller_prefix), read_handle)

    repo = Repo(Name(config['repo_config']['repo_name']),
                face, storage, read_handle, cmd_handle)
    repo.recover_previous_context()

    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(face_loop())
    finally:
        event_loop.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

# pr.disable()
# s = io.StringIO()
# sortby = SortKey.CUMULATIVE
# ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
# ps.print_stats()
# print(s.getvalue())
