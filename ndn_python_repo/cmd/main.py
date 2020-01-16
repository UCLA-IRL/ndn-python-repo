import sys
import logging
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn_python_repo import *


def main() -> int:
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    try:
        config = get_yaml()
        logging.info(config)

        app = NDNApp()

        storage = SqliteStorage(config['db_config']['sqlite3']['path'])
        read_handle = ReadHandle(app, storage)
        write_handle = WriteCommandHandle(app, storage, read_handle)
        delete_handle = DeleteCommandHandle(app, storage)
        tcp_bulk_insert_handle = TcpBulkInsertHandle(storage, read_handle,
                                                     config['tcp_bulk_insert']['addr'],
                                                     config['tcp_bulk_insert']['port'])

        repo = Repo(Name.from_str(config['repo_config']['repo_name']),
                    app, storage, read_handle, write_handle, delete_handle, tcp_bulk_insert_handle)
        repo.listen()

        app.run_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
