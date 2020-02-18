import argparse
import logging
import pkg_resources
import sys
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn_python_repo import *


def process_cmd_opts():
    """
    Parse, process, and return cmd options.
    """
    def print_version():
        pkg_name = 'ndn-python-repo'
        version = pkg_resources.require(pkg_name)[0].version
        print(pkg_name + ' ' + version)

    def parse_cmd_opts():
        parser = argparse.ArgumentParser(description='ndn-python-repo')
        parser.add_argument('-v', '--version',
                            help='print current version and exit', action='store_true')
        parser.add_argument('-c', '--config',
                            help='override default config file')
        args = parser.parse_args()
        return args

    args = parse_cmd_opts()
    if args.version:
        print_version()
        exit(0)
    return args


def main() -> int:
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    args = process_cmd_opts()
    config = get_yaml(args.config)
    logging.info(config)

    storage = StorageFactory.create_storage_handle(config['db_config'])

    app = NDNApp()

    read_handle = ReadHandle(app, storage)
    write_handle = WriteCommandHandle(app, storage, read_handle)
    delete_handle = DeleteCommandHandle(app, storage)
    tcp_bulk_insert_handle = TcpBulkInsertHandle(storage, read_handle,
                                                    config['tcp_bulk_insert']['addr'],
                                                    config['tcp_bulk_insert']['port'])

    repo = Repo(Name.from_str(config['repo_config']['repo_name']),
                app, storage, read_handle, write_handle, delete_handle, tcp_bulk_insert_handle)
    repo.listen()

    try:
        app.run_forever()
    except FileNotFoundError:
        print('Error: could not connect to NFD.')
    return 0


if __name__ == "__main__":
    sys.exit(main())
