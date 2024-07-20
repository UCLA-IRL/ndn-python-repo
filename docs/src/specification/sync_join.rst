Sync Join
=========

The sync join protocol is used to command the repo to join a state vector sync group.

1. The repo subscribes to the topic ``/<repo_name>/sync/join``.

2. The client publishes a message to the topic ``/<repo_name>/sync/join``. The message payload is of type
   ``RepoCommandParam``, containing one or more ``SyncParam`` with the following fields:

  * ``sync_prefix``: The name prefix of the sync group to join.
  * ``register_prefix``: (Optional) The name prefix for the repo to register with the forwarder. This prefix must not
    be the same as ``sync_prefix``.
  * ``data_name_dedupe``: (Optional) If true, the repo will deduplicate data names in the sync group.
  * ``reset``: (Optional) If true, rebuild state vectors from the stored state vectors on the repo disk. This is useful
    if interests are sent for permanently unavailable data from an old vector.

3. The repo joins the sync group, saving sync information to disk.

  * The repo will listen for state vector interests for the sync group. Then, to fetch any data, the repo will send
    interests following the SVSPS data naming convention. For more information, see the
    `specification page <https://named-data.github.io/StateVectorSync/Specification.html>`_ for State Vector
    Synchronization.