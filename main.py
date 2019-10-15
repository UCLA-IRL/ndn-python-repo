#!./venv/bin/python3
import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, Component

from src import *

DO_PROFILING = False
if DO_PROFILING:
    import cProfile, pstats, io
    from pstats import SortKey
    pr = cProfile.Profile()
    pr.enable()



def main():
    config = get_yaml()
    logging.info(config)

    app = NDNApp()

    storage = MongoDBStorage(config['db_config']['mongodb']['db'], config['db_config']['mongodb']['collection'])
    read_handle = None
    write_handle = WriteCommandHandle(app, storage, read_handle)
    delete_handle = None
    tcp_bulk_insert_handle = None

    repo = Repo(Name.from_str(config['repo_config']['repo_name']),
                app, storage, read_handle, write_handle, delete_handle, tcp_bulk_insert_handle)
    repo.listen()

    app.run_forever()


if __name__ == "__main__":
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)
    try:
        main()
    except KeyboardInterrupt:
        pass



if DO_PROFILING:
    pr.disable()
    s = io.StringIO()
    sortby = SortKey.CUMULATIVE
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats()
    print(s.getvalue())