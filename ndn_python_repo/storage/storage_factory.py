"""
    Factory for storage handles.

    @Author jonnykong@cs.ucla.edu
    @Date   2020-02-16
"""

from .sqlite import SqliteStorage

# import only supported storage backends
try:
    from .leveldb import LevelDBStorage
except ImportError as exc:
    pass

try:
    from .mongodb import MongoDBStorage
except ImportError as exc:
    pass


def create_storage(config):
    """
    Factory method to create storage handle.
    :param config: config object created by parsing yaml
    :return: handle
    """
    db_type = config['db_type']
    
    try:
        if db_type == 'sqlite3':
            db_path = config[db_type]['path']
            ret = SqliteStorage(db_path)
        elif db_type == 'leveldb':
            db_dir = config[db_type]['dir']
            ret = LevelDBStorage(db_dir)
        elif db_type == 'mongodb':
            db_name = config[db_type]['db']
            db_collection = config[db_type]['collection']
            ret = MongoDBStorage(db_name, db_collection)
        else:
            raise NameError()

    except NameError as exc:
        raise NotImplementedError(f'Unsupported database backend: {db_type}')
    
    return ret