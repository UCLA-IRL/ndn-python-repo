import pytest
import subprocess
from subprocess import STDOUT


class RepoTestSuite:
    app = None

    def start_repo_instance(self):
        subprocess.run('ndn-python-repo', stderr=STDOUT)
        print("Running")

    def test_main(self):
        pass