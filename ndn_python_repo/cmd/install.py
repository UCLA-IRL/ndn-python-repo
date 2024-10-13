import platform
import shutil
import sys
import importlib.resources


def install(source, destination):
    shutil.copy(source, destination)
    print(f'Installed {source} to {destination}')

def main():
    # systemd for linux
    if platform.system() == 'Linux':
        resource = importlib.resources.files('ndn_python_repo').joinpath('ndn-python-repo.service')
        # source = resource_filename(__name__, '../ndn-python-repo.service')
        destination = '/etc/systemd/system/'
        with importlib.resources.as_file(resource) as source:
            install(source, destination)


if __name__ == "__main__":
    sys.exit(main())