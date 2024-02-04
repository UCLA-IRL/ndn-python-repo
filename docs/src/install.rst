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

For development, `poetry <https://python-poetry.org/>`_ is recommended.

.. code-block:: bash

    $ poetry install --all-extras

To setup a traditional python3 virtual environment with editable installation:

.. code-block:: bash

    python3 -m venv venv
    . venv/bin/activate
    pip3 install -e ".[dev,docs]"

Run all tests:

.. code-block:: bash

    $ nfd-start
    $ pytest tests

Compile the documentation with Sphinx:

.. code-block:: bash

    $ poetry run make -C docs html
    $ open docs/_build/html/index.html
