.. _specification-delete-label:

Delete
======

The repo deletion process makes use of the ``PubSub`` module:

1. Repo subscribe to topic ``/<repo_name>/delete``.

2. The client publishes a message to topic to ``/<repo_name>/delete``. This
message is in format ``RepoCommandParameter``, and the following parameters
are relevant:

* ``name``: The prefix of the data to delete.

* ``start_block_id``: The start segment number of the data to delete.

* ``end_block_id``: The end segment number of the data to delete.

* ``process_id``: A random id generated on the client side to identify this deletion process.

* ``register_prefix`` (Optional). If repo doesn't register the root prefix, client can tell repo to unregister this prefix.

3. The repo deletes the data with the following behavior:

* If neither ``start_block_id`` nor ``end_block_id`` is given, the repo deletes a single data packet named ``/name``. The process is deemed successful if this data packet is deleted.

* If ``end_block_id`` is not given, the repo attempts to delete all segments starting from ``/name/start_block_id``, until encountering a non-existing segment. In this scenario, the process is always assumed to be successful.

* Otherwise, the repo deletes all data segments between ``/name/start_block_id`` and ``/name/end_block_id`` inclusive. If ``start_block_id`` is not given, it is set to 0. The process is successful if all packets are deleted.


Delete status check
-------------------

To check the status of a deletion process, the client can check its status 
using the deletion check protocol.
The deletion check response is a message in ``RepoCommandResponse`` format,
where the following parameters are relevant:

* ``status_code``: The status code of the process. For status code definitions, please refer to :ref:`specification-check-label`.

* ``delete_num``: The number of data packets that was deleted by the repo.