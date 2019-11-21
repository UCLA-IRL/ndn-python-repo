import logging
import os
import yaml


def get_yaml():
    path = '/usr/local/etc/ndn/ndn-repo.conf'
    if not os.path.exists(path):
        path = '_config.yaml'
        
    try:
        with open(path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        return config
    except Exception as exception:
        logging.warning(str(exception))
        logging.warning('failed to parse config file')


# For testing
if __name__ == "__main__":
    print(get_yaml())

