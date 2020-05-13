Install and Run
===============

Install
-------

Install the latest release with pip:

.. code-block:: bash

    $ /usr/bin/pip3 install ndn-python-repo

Optionally, you can install the latest development version from source:

.. code-block:: bash

    $ git clone https://github.com/JonnyKong/ndn-python-repo.git
    $ cd ndn-python-repo && /usr/bin/pip3 install -e .


Migrate from repo-ng
--------------------

ndn-python-repo provides a script to migrate existing data from repo-ng::

    $ ndn-python-repo-port -d <path-to-repo-ng-dbfile> \
                           -a <ndn-python-repo-ipaddr> \
                           -p <ndn-python-repo-port>

It takes as input a repo-ng database file, reads the Data packets and pipe them through TCP bulk insert into the new repo.


Instruction for developers
--------------------------

Run all tests:

.. code-block:: bash

    $ pytest

Compile the documentation with Sphinx:

.. code-block:: bash

    $ cd docs && make html
    $ open _build/html/index.html