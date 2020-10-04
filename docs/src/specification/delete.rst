.. _specification-delete-label:

Delete
======

Repo deletion process makes use of the :doc:`../misc_pkgs/pub_sub`.

1. The repo subscribes to the topic ``/<repo_name>/delete``.

2. The client publishes a message to the topic ``/<repo_name>/delete``.
   The message payload is ``RepoCommandParameter`` with the following fields:

  * ``name``: either a Data packet name, or a name prefix of Data packets.
  * ``start_block_id`` (Optional): inclusive start segment number.
  * ``end_block_id`` (Optional): inclusive end segment number.
  * ``register_prefix`` (Optional): if repo doesn't register the root prefix (:doc:`../configuration` ``register_root`` is disabled), client can tell repo to unregister this prefix.
  * ``check_prefix``: a prefix of status check topic name. See :doc:`check`.
  * ``process_id``: a random byte string to identify this deletion process.

3. The repo deletes Data packets according to given parameters.

  * If both ``start_block_id`` and ``end_block_id`` are omitted, the repo deletes a single packet identified in ``name`` parameter.
    The deletion process succeeds when this packet is deleted.
  * If ``start_block_id`` is specified but ``end_block_id`` is omitted, the repo starts deleting segments starting from ``/name/start_block_id``, and increments segment number after each packet.
    When a name query does not find an existing segment, the deletion process stops and is considered successful.
  * Otherwise, the repo fetches all segments between ``/name/start_block_id`` and ``/name/end_block_id``.
    If ``start_block_id`` is omitted, it defaults to 0.
    The deletion process succeeds when all packets are deleted.
  * Segment numbers are encoded in accordance with `NDN naming conventions rev2 <https://named-data.net/publications/techreports/ndn-tr-22-2-ndn-memo-naming-conventions/>`_.


Delete status check
-------------------

The client can use the :doc:`check` protocol to check the progress of a deletion process.
The deletion check response message payload is ``RepoCommandResponse`` with the following fields:

* ``status_code``: status code, as defined on :doc:`check`.
* ``delete_num``: number of Data packets deleted by the repo so far.
