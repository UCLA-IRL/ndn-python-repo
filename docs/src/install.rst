Install and Run
===============

Install the latest release with pip:

.. code-block:: bash

    $ /usr/bin/pip3 install ndn-python-repo

Optionally, you can install the latest development version from source:

.. code-block:: bash

    $ git clone https://github.com/JonnyKong/ndn-python-repo.git
    $ cd ndn-python-repo && /usr/bin/pip3 install -e .

Instruction for developers
--------------------------

Run all tests:

.. code-block:: bash

    $ pytest

Compile the documentation with Sphinx:

.. code-block:: bash

    $ cd docs && make html
    $ open _build/html/index.html