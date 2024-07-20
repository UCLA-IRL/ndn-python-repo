Sync Leave
==========

The sync leave protocol is used to command the repo to leave the sync group. This command also removes any information
about the sync group from repo storage.

1. The repo subscribes to the topic ``/<repo_name>/sync/leave``.

2. The client publishes a message to the topic ``/<repo_name>/sync/leave``. The message payload is of type
   ``RepoCommandParam``, containing one or more ``SyncParam`` with the following field:

  * ``sync_prefix``: The name prefix of the sync group to leave.

3. The repo leaves the sync group, removing sync information from disk. The repo no longer listens to the originally
   specified register prefix.

  * Note that any already-stored data packets that were received prior to leaving the sync group are *not* deleted.