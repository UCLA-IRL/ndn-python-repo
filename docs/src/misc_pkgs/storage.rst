``Storage`` package
===================

ndn-python-repo supports 3 types of databases as backends.
The ``Storage`` package provides a unified key-value storage API with the following features:

* Supports ``MustBeFresh``
* Supports ``CanBePrefix``
* Batched writes with periodic writebacks to improve performance

The ``Storage`` class provides an interface, and is implemented by:

* ``SqliteStorage``
* ``LevelDBStorage``
* ``MongoDBStorage``

Note that the type ``Union[Iterable[Union[bytes, bytearray, memoryview, str]], str, bytes, bytearray, memoryview]`` 
in the documentation is equivalent to the ``ndn.name.NonStrictName`` type.

Reference
---------

.. autoclass:: ndn_python_repo.storage.Storage
    :members:

.. autoclass:: ndn_python_repo.storage.SqliteStorage
    :members:

.. autoclass:: ndn_python_repo.storage.LevelDBStorage
    :members:

.. autoclass:: ndn_python_repo.storage.MongoDBStorage
    :members: