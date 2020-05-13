``PubSub`` package
==================

Introduction
------------

The ``PubSub`` package provides a pub-sub API with best-effort, at-most-once delivery guarantee.

If there are no subscribers reachable when a message is published, this message will not be
re-transmitted.

If there are multiple subscribers reachable, the nearest subscriber will be notified of the
published message in an any-cast style.

Note that the type ``Union[Iterable[Union[bytes, bytearray, memoryview, str]], str, bytes, bytearray, memoryview]`` 
in the documentation is equivalent to the ``ndn.name.NonStrictName`` type.

Reference
---------

.. autoclass:: ndn_python_repo.utils.PubSub
    :members: