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


Process
-------

Under the hood the ``PubSub`` module transmits a series of Interest and Data packets:

1. When the subscriber calls ``subscribe(topic, cb)``. This makes the subcriber listen on
``"/<topic>/notify"``.

2. When the publisher invokes ``publish(topic, msg)``. This method sends an Interest with name
``“/<topic>/notify”``, which will be routed to a subscriber. The interest carries:

    * Publisher prefix: used by the subscriber to reach the publisher in the next step
    * Nonce: used by the publisher to de-multiplex among different publications
    * Forwarding hint (optional): if publisher prefix is not announced in the routing system, publisher can provide a forwarding hint

    Meanwhile, ``msg`` is wrapped into a Data packet named ``"/<pub_prefix>/msg/<nonce>"``.

3. The subscriber receives the notification interest, constructs a new Interest
``"/<pub_prefix>/msg/<nonce>"`` and send it to the publisher.

4. The publisher receives the interest ``"/<pub_prefix>/msg/<nonce>"``, and returns the
corresponding data.

5. The subscriber receives the data, and invokes ``cb(data.content)`` to hand the message to the
application. 

6. The publisher receives the acknowledgement Data packet, and erases the soft state.


Reference
---------

.. autoclass:: ndn_python_repo.utils.PubSub
    :members: