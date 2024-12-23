.. _specification-insert-label:

Insert
======

Repo insertion process makes use of the :doc:`../misc_pkgs/pub_sub`.

1. The repo subscribes to the topic ``/<repo_name>/insert``.

2. The client publishes a message to the topic ``/<repo_name>/insert``.
   The message payload is ``RepoCommandParam`` containing one or more ``ObjParam`` with the following fields:

      * ``name``: either a Data packet name, or a name prefix of segmented Data packets.
      * ``start_block_id`` (Optional): inclusive start segment number.
      * ``end_block_id`` (Optional): inclusive end segment number.
      * ``forwarding_hint`` (Optional): forwarding hint for Data fetching.
       This is useful in two scenarios:

       * The producer choose not to announce its name prefix, but only allow the repo to reach it via forwarding hint.
       * The name prefix is already announced by repo node(s), but the producer in another node wants to insert to the repo.

      * ``register_prefix`` (Optional): if repo doesn't register the root prefix (:doc:`../configuration` ``register_root`` is disabled), client can tell repo to register this prefix.

3. The repo fetches and inserts single or segmented Data packets according to given parameters.

  * If neither ``start_block_id`` nor ``end_block_id`` are given, the repo fetches a single packet identified in ``name`` parameter.
    The insertion process succeeds when this packet is received.
  * If only ``end_block_id`` is given, ``start_block_id`` is considered 0.
  * If only ``start_block_id`` is given, ``end_block_id`` is auto detected, i.e. infinity.
  * If both block ids are given, the command is considered as correct only if ``end_block_id >= start_block_id``.
  * Whenever the repo cannot fetch a segment, it will stop, no matter what ``end_block_id`` is.
  * Segment numbers are encoded in accordance with `NDN naming conventions rev2 <https://named-data.net/publications/techreports/ndn-tr-22-2-ndn-memo-naming-conventions/>`_.


Insert status check
-------------------

The client can use the :doc:`check` protocol to check the progress of an insertion process.
The insertion check response message payload is ``RepoCommandRes`` containing zero or more
``ObjStatus`` with the following fields:

* ``status_code``: status code, as defined on :doc:`check`.
  Both the command itself and objects has a status code.
* ``name``: the name of object to insert.
* ``insert_num``: number of Data packets received by the repo so far.
* The number of ``ObjStatus`` in the result should be either:
  * =0, which means the command is malformed or not allowed.
  * equals to the number of ``ObjParam`` in the insertion command.
