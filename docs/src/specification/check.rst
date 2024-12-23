Check
=====

The check protocol is used by clients to check the progress of a insertion or deletion process.

1. The check prefix for ``<command>`` is ``/<repo_name>/<command> check``.
   For example, the check prefix for insertion is ``/<repo_name>/insert check``,
   and deletion is ``/<repo_name>/delete check``.
2. Status check Interests are send to the check prefix directly. No Pub-Sub is used here.
3. The check Interest should carry an application parameter ``RepoStatQuery``,
   which contains the request number of the command.
   The request number of the command is always the SHA256 hash of the command data published in Pub-Sub.
4. After receiving the query Interest, the repo responds with a Data packet containing ``RepoCommandRes``.
5. The status is only kept for 60s after the operation finishes.
   After that time, all queries will be responded with ``NOT-FOUND``.

RepoCommandRes
==============

* The ``RepoCommandRes`` Data contains a status code for the whole command, with the following rules:

  * ``MALFORMED``: If the command cannot be parsed.
  * ``NOT-FOUND``: If the given request no is not associated with a valid command.
    This is also returned when the repo has not finish fetching the command from Pub-Sub,
    or the command has finished for more than 60s.
  * ``COMPLETED``: If all operations (for all objects) completed.
  * ``IN-PROGRESS``: The command is received and being executed.
  * ``FAILED``: If one or more operation in the command fails.
    If the is insertion, this means some or all objects requested to insert cannot be completely fetched.
    However, fetched objects or segments are still inserted into the repo.
    Only the objects with ``insert_num=0`` are not inserted.

* For each ``ObjStatus`` contained in the ``RepoCommandRes``, the status code can be one of the following:

  * ``ROGER``: The whole command is received and the operation on this object will be started in the future.
  * ``MALFORMED``: If the object has wrong parameter.
  * ``FAILED``: If the operation on this object failed to execute.
    For example, not all segments specified can be fetched.
    Note that even for a failed object, fetched segments are still put into the repo and can be fetched.
  * ``COMPLETED``: If the operation on this object succeeded.
