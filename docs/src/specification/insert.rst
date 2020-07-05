.. _specification-insert-label:

Insert
======

The repo insertion process makes use of the ``PubSub`` module:

1. Repo subscribe to topic ``/<repo_name>/insert``.

2. The client publishes a message to topic to ``/<repo_name>/insert``. This
message is in format ``RepoCommandParameter``, and the following parameters
are relevant:

* ``name``: The prefix of the data to insert.

* ``forwarding_hint`` (Optional). The forwarding hint used when repo fetches the data. This is useful in two scenarios: 1) the producer choose not to announce its name prefix, but only allow the repo to reach it via forwarding hint, or 2) the data is already announced by the repo node(s), while the producer in another node wants to insert to the repo.
    
* ``start_block_id`` (Optional). The start segment number of the data to insert.

* ``end_block_id`` (Optional). The end segment number of the data to insert.

* ``process_id``. A random byte string generated on the client side to identify this insertion process.

* ``register_prefix`` (Optional). If repo doesn't register the root prefix, client can tell repo to register this prefix.

* ``check_prefix``. Repo will publish status check messages under ``<check_prefix>/<process_id>``.

3. The repo fetches the data with the following behavior:

* If neither ``start_block_id`` nor ``end_block_id`` is given, the repo fetches a single data packet named ``/name``. The process is deemed successful if this data packet is received.

* If ``end_block_id`` is not given, the repo attempts to fetch all segments starting from ``/name/start_block_id``, until an interest receives timeout or nack 3 times. In this scenario, the process is always assumed to be successful.

* Otherwise, the repo fetches all data segments between ``/name/start_block_id`` and ``/name/end_block_id`` inclusive. If ``start_block_id`` is not given, it is set to 0. The process is successful if all packets are received.


Insert status check
-------------------

To check the status of a insertion process, the client can check its status 
using the insertion check protocol.
The insertion check response is a message in ``RepoCommandResponse`` format,
where the following parameters are relevant:

* ``status_code``: The status code of the process. For status code definitions, please refer to :ref:`specification-check-label`.

* ``insert_num``: The number of data packets that was received by the repo.
