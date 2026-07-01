.. _specification-ingest-label:

Ingest
======

The direct ingest protocol is a lightweight command/response alternative to :doc:`insert`,
for high-throughput producers. It does not use :doc:`../misc_pkgs/pub_sub`: the repo listens
for Interests directly, and each command is a single Interest/Data exchange.

1. The repo registers an Interest filter on ``/<repo_name>/ingest``.

2. The producer sends an Interest under ``/<repo_name>/ingest`` carrying an application
   parameter ``IngestCmdParam``. NDN appends a ``params-sha256=<digest>`` component computed
   over the parameter, making the Interest name unique per command, with the following fields:

   * ``data_name``: either a Data packet name, or a name prefix of segmented Data packets.
   * ``forwarding_hint`` (Optional): forwarding hint used to fetch ``data_name``, same
     semantics as in :doc:`insert`.
   * ``start_block_id`` (Optional): inclusive start segment number.
   * ``end_block_id`` (Optional): inclusive end segment number.
   * ``register_prefix`` (Optional): tell the repo to start serving reads under this prefix
     once the data is stored.
   * ``ingest_nonce`` (Optional): reserved for future use; currently ignored by the repo.

3. The repo fetches and stores Data following the same rules as :doc:`insert`:

   * If neither block id is given, the repo fetches the single packet identified by
     ``data_name``.
   * If only ``end_block_id`` is given, ``start_block_id`` is considered 0.
   * If only ``start_block_id`` is given, ``end_block_id`` is auto-detected, i.e. infinity.
   * If both are given, the command is valid only when ``end_block_id >= start_block_id``.
   * Segment numbers follow `NDN naming conventions rev2
     <https://named-data.net/publications/techreports/ndn-tr-22-2-ndn-memo-naming-conventions/>`_.

4. Once all requested packets are fetched and stored, the repo acks by replying to the
   original ingest Interest with an empty Data packet.

5. If fetching fails, the repo sends **no** reply; the producer's Interest timeout is the only
   failure signal, and it must resend the command to retry. There is no status/check protocol
   for ingest (contrast with :doc:`check`, available for :doc:`insert` and :doc:`delete`).

.. note::
   ``register_prefix`` registrations are kept only in memory, not persisted like
   :doc:`insert`, and are lost on repo restart. Also, unlike :doc:`insert`, the repo does not
   check whether ``data_name`` overlaps with its own ``/<repo_name>`` namespace.
