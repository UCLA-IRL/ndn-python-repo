import yaml
# from pkg_resources import resource_filename
import importlib.resources


def get_yaml(path=None):
    # if fall back to internal config file, so that repo can run without any external configs
    
        
    try:
        if path is None:
            resource = importlib.resources.files('ndn_python_repo').joinpath('ndn-python-repo.conf.sample')
            with resource.open('r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
        else:
            with open(path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f'could not find config file: {path}') from None
    return config


# For testing
if __name__ == "__main__":
    print(get_yaml())
