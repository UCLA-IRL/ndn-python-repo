import argparse
import asyncio as aio
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
                            help='path to config file')
        parser.add_argument('-r', '--repo_name',
                            help="""repo's routable prefix. If this option is specified, it 
                                    overrides the prefix in the config file""")
        args = parser.parse_args()
        return args

    args = parse_cmd_opts()
    if args.version:
        print_version()
        exit(0)
    return args


def process_config(cmdline_args):
    """
    Read and process config file. Some config options are overridden by cmdline args.
    """
    config = get_yaml(cmdline_args.config)
    if cmdline_args.repo_name != None:
        config['repo_config']['repo_name'] = cmdline_args.repo_name
    return config


def main() -> int:
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    cmdline_args = process_cmd_opts()
    config = process_config(cmdline_args)
    logging.info(config)

    storage = create_storage(config['db_config'])

    app = NDNApp()

    read_handle = ReadHandle(app, storage)
    write_handle = WriteCommandHandle(app, storage, read_handle)
    delete_handle = DeleteCommandHandle(app, storage, read_handle)
    tcp_bulk_insert_handle = TcpBulkInsertHandle(storage, read_handle,
                                                    config['tcp_bulk_insert']['addr'],
                                                    config['tcp_bulk_insert']['port'])

    repo = Repo(Name.from_str(config['repo_config']['repo_name']),
                app, storage, read_handle, write_handle, delete_handle, tcp_bulk_insert_handle)
    aio.ensure_future(repo.listen())

    try:
        app.run_forever()
    except FileNotFoundError:
        print('Error: could not connect to NFD.')
    return 0


if __name__ == "__main__":
    sys.exit(main())
