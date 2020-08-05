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

1. The subscriber calls ``subscribe(topic, cb)``. This makes the subcriber listen on
``"/<topic>/notify"``.

2. The publisher invokes ``publish(topic, msg)``. This method sends an Interest with name
``"/<topic>/notify"``, which will be routed to a subscriber. The interest carries the following fields in its application parameters:

    * Publisher prefix: used by the subscriber to reach the publisher in the next step
    * NotifyNonce: a random bytes string, used by the publisher to de-multiplex among different publications
    * Forwarding hint (optional): if publisher prefix is not announced in the routing system, publisher can provide a forwarding hint

    Meanwhile, ``msg`` is wrapped into a Data packet named ``"/<pub_prefix>/msg/<topic>/<notify_nonce>"``. Here, the data name contains ``topic`` to establish a binding between topic and nonce, to prevent man-in-the-middle attacks that changes the topic.

3. The subscriber receives the notification interest, constructs a new Interest
``"/<pub_prefix>/msg/<topic>/<notify_nonce>"`` and send it to the publisher.

4. The publisher receives the interest ``"/<pub_prefix>/msg/<topic>/<notify_nonce>"``, and returns the
corresponding data.

5. The subscriber receives the data, and invokes ``cb(data.content)`` to hand the message to the
application. 

6. The publisher receives the acknowledgement Data packet, and erases the soft state.


Encoding
--------

The notify Interest's application parameter is encoded as follows:

.. code-block::

    NotifyAppParam = DATA-TYPE TLV-LENGTH
        [PublisherPrefix]
        [NotifyNonce]
        [PublisherFwdHint]

    PublisherPrefix = Name

    NotifyNonce = NOTIFY-NONCE-TYPE TLV-LENGTH Bytes

    PublisherFwdHint = PUBLISHER-FWD-HINT-TYPE TLV-LENGTH Name

The type number assignments are as follows:

    +---------------------------+----------------------------+--------------------------------+
    | type                      | Assigned number (decimal)  | Assigned number (hexadecimal)  |
    +===========================+============================+================================+
    | NOTIFY-NONCE-TYPE         | 128                        | 0x80                           |
    +---------------------------+----------------------------+--------------------------------+
    | PUBLISHER-FWD-HINT-TYPE   | 211                        | 0xD3                           |
    +---------------------------+----------------------------+--------------------------------+


Reference
---------

.. autoclass:: ndn_python_repo.utils.PubSub
    :members:
