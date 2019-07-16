import yaml
import logging


def get_yaml():
    path = '_config.yaml'
    try:
        with open(path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        print('parsing success')
        return config
    except Exception as exception:
        logging.warning(str(exception))
        logging.warning('failed to parse config file')


# For testing
if __name__ == "__main__":
    print(get_yaml())

