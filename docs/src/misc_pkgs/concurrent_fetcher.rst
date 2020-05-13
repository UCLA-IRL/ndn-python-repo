``ConcurrentFetcher`` package
=============================

Introduction
------------

Fetch data packets in parallel using a fixed window size.

Note that the type ``Union[Iterable[Union[bytes, bytearray, memoryview, str]], str, bytes, bytearray, memoryview]`` 
in the documentation is equivalent to the ``ndn.name.NonStrictName`` type.


Reference
---------

.. autofunction:: ndn_python_repo.utils.concurrent_fetcher