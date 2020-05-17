.. _specification-check-label:

Check
=====

The check protocols is used by the clients to check the status of a 
insertion or deletion process.

1. The repo listens on prefixes ``/<repo_name>/check insert`` and ``/<repo_name>/check delete``.

2. Taking insertion check for example, the client sends an interest ``/<repo_name>/check insert/<param>``. Here, ``param`` is a ``RepoCommandParameter`` encoded in TLV format, and the following fields are relevant:

    * ``process_id``: The id of the process to check.

3. The repo responds with a data packet. The content of the data packet is a ``RepoCommandResponse`` encoded in TLV format.