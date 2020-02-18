import logging
import os
import yaml
from pkg_resources import resource_filename


def get_yaml(path):
    if path == None:
        path = '/usr/local/etc/ndn/ndn-python-repo.conf'
        
    try:
        with open(path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f'could not find config file: {path}') from None
    return config


# For testing
if __name__ == "__main__":
    print(get_yaml())

