Configuration
=============

You can configure ndn-python-repo with a config file, by specifying the path to the file when
starting a repo instance:

.. code-block:: bash

    $ ndn-python-repo -c <config_file>

A sample config file is provided at ``ndn_python_repo/ndn-python-repo.conf.sample``.

If no config file is given on the command line, this sample config file will be used by default.


Repo namespace
--------------

Specify the name of a repo in the config file. For example::

    repo_config:
      # the repo's routable prefix
      repo_name: 'testrepo'

Another option is to specify the repo name when starting a repo on the command line.
This overrides the repo name in the config file::

    $ ndn-python-repo -r "/name_foo"


Repo prefix registration
------------------------
By default, the repo registers the root prefix ``/``.

Alternatively, you can configure repo such that it doesn't register the root prefix::

    repo_config:
      register_root: False
    
If ``register_root`` is set to ``False``, the client is responsible of telling the
repo which prefix to register or unregister every time in ``RepoCommandParameter``.
See :ref:`specification-insert-label` and :ref:`specification-delete-label` for details.


Choose the backend database
---------------------------

The ndn-python-repo uses one of the three backend databases:

* SQLite3 (default)
* leveldb
* MongoDB

To use non-default databases, perform the following steps:

#. Install ndn-python-repo with additional database support that you need::

    $ /usr/bin/pip3 install ndn-python-repo[leveldb]
    $ /usr/bin/pip3 install ndn-python-repo[mongodb]

#. Specify the database selection and database file in the config file. For example::

    db_config:
      # choose one among sqlite3, leveldb, and mongodb
      db_type: 'mongodb'

      # only the chosen db's config will be read
      mongodb:
        'db': 'repo'
        'collection': 'data'


TCP bulk insert
---------------

By default, the repo listens on ``0.0.0.0:7376`` for TCP bulk insert.
You can configure in the config file which address the repo listens on. For example::

    tcp_bulk_insert:
      'addr': '127.0.0.1'
      'port': '7377'


Logging
-------

Repo uses the python logging module, and by default logs all messages of and above
level ``INFO`` to ``stdout``.
You can override the default options in the config file. For example::

    logging_config:
      'level': 'WARNING'
      'file': '/var/log/ndn/ndn-python-repo/repo.log'


systemd
----------------

To run ndn-python-repo with systemd on Linux, perform the following steps:

#. Run the provided script to install the systemd script to ``/etc/systemd/system/``::

    $ sudo ndn-python-repo-install

#. Then, start, stop, and monitor a repo instance with systemd::

    $ sudo systemctl start ndn-python-repo
    $ sudo systemctl stop ndn-python-repo
    $ sudo systemctl status ndn-python-repo

#. Examine logs::

    $ sudo journalctl -u ndn-python-repo.service