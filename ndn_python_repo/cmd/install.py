import os
import platform
import shutil
import sys
from pkg_resources import resource_filename


def install(source, destination):
    shutil.copy(source, destination)
    print(f'Installed {source} to {destination}')

def main():
    # systemd for linux
    if platform.system() == 'Linux':
        source = resource_filename(__name__, '../ndn-python-repo.service')
        destination = '/etc/systemd/system/'
        install(source, destination)


if __name__ == "__main__":
    sys.exit(main())