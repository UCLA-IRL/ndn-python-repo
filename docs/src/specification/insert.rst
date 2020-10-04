.. _specification-insert-label:

Insert
======

Repo insertion process makes use of the :doc:`../misc_pkgs/pub_sub`.

1. The repo subscribes to the topic ``/<repo_name>/insert``.

2. The client publishes a message to the topic ``/<repo_name>/insert``.
   The message payload is ``RepoCommandParameter`` with the following fields:

  * ``name``: either a Data packet name, or a name prefix of Data packets.
  * ``start_block_id`` (Optional): inclusive start segment number.
  * ``end_block_id`` (Optional): inclusive end segment number.
  * ``forwarding_hint`` (Optional): forwarding hint for Data fetching.
    This is useful in two scenarios:

    * The producer choose not to announce its name prefix, but only allow the repo to reach it via forwarding hint.
    * The name prefix is already announced by repo node(s), but the producer in another node wants to insert to the repo.

  * ``register_prefix`` (Optional): if repo doesn't register the root prefix (:doc:`../configuration` ``register_root`` is disabled), client can tell repo to register this prefix.
  * ``check_prefix``: a prefix of status check topic name. See :doc:`check`.
  * ``process_id``: a random byte string to identify this insertion process.

3. The repo fetches and inserts Data packets according to given parameters.

  * If both ``start_block_id`` and ``end_block_id`` are omitted, the repo fetches a single packet identified in ``name`` parameter.
    The insertion process succeeds when this packet is received.
  * If ``start_block_id`` is specified but ``end_block_id`` is omitted, the repo starts fetching segments starting from ``/name/start_block_id``, and increments segment number after each packet.
    When an Interest receives timeout or nack 3 times, the insertion process stops and is considered successful.
  * Otherwise, the repo fetches all segments between ``/name/start_block_id`` and ``/name/end_block_id``.
    If ``start_block_id`` is omitted, it defaults to 0.
    The insertion process succeeds when all packets are received.
  * Segment numbers are encoded in accordance with `NDN naming conventions rev2 <https://named-data.net/publications/techreports/ndn-tr-22-2-ndn-memo-naming-conventions/>`_.


Insert status check
-------------------

The client can use the :doc:`check` protocol to check the progress of an insertion process.
The insertion check response message payload is ``RepoCommandResponse`` with the following fields:

* ``status_code``: status code, as defined on :doc:`check`.
* ``insert_num``: number of Data packets received by the repo so far.
