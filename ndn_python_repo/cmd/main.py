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


def config_logging(config: dict):
    log_levels = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG
    }

    # default level is INFO
    if config['level'] not in log_levels:
        log_level = logging.INFO
    else:
        log_level = log_levels[config['level']]
    
    # default is stdout
    log_file = config['file'] if 'file' in config else None

    if not log_file:
        logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=log_level)
    else:
        logging.basicConfig(filename=log_file,
                            format='[%(asctime)s]%(levelname)s:%(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=log_level)


def main() -> int:
    cmdline_args = process_cmd_opts()
    config = process_config(cmdline_args)
    print(config)

    config_logging(config['logging_config'])

    storage = create_storage(config['db_config'])

    app = NDNApp()

    pb = PubSub(app)
    read_handle = ReadHandle(app, storage, config)
    write_handle = WriteCommandHandle(app, storage, pb, read_handle, config)
    delete_handle = DeleteCommandHandle(app, storage, pb, read_handle, config)
    tcp_bulk_insert_handle = TcpBulkInsertHandle(storage, read_handle, config)

    repo = Repo(app, storage, read_handle, write_handle, delete_handle, tcp_bulk_insert_handle, config)
    aio.ensure_future(repo.listen())

    try:
        app.run_forever()
    except FileNotFoundError:
        print('Error: could not connect to NFD.')
    return 0


if __name__ == "__main__":
    sys.exit(main())
