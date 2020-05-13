Client-side packages
====================

Introduction
------------

Application built with python-ndn can make use of the client packages provided.

There are four parts:

#. **PutfileClient**: insert files into the repo.
#. **GetfileClient**: get files from the repo.
#. **DeleteClient**: detele data packets from the repo.
#. **CommandChecker**: check process status from the repo.

The example programs in :mod:`examples/` illustrate how to use these packages.

Note that the type ``Union[Iterable[Union[bytes, bytearray, memoryview, str]], str, bytes, bytearray, memoryview]`` 
in the documentation is equivalent to the ``ndn.name.NonStrictName`` type.



Reference
---------

.. automodule:: ndn_python_repo.clients.putfile

    .. autoclass:: PutfileClient
        :members:

.. automodule:: ndn_python_repo.clients.getfile

    .. autoclass:: GetfileClient
        :members:

.. automodule:: ndn_python_repo.clients.delete

    .. autoclass:: DeleteClient
        :members:

.. automodule:: ndn_python_repo.clients.command_checker

    .. autoclass:: CommandChecker
        :members: