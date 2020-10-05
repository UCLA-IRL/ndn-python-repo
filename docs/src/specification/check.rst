Check
=====

The check protocol is used by clients to check the progress of a insertion or deletion process.

1. Each insert/delete command has ``check_prefix`` and ``process_id`` parameters.
   Status check messages are published to the topic ``/<check_prefix>/check/<process_id>``, derived from these parameters.
2. After receiving an insert/delete command, the repo periodically publishes the status of the insertion/deletion process to the topic.
   The message payload is ``RepoCommandResponse``.
3. The client can subscribe to the topic to receive status updates.

Status Code Definition
----------------------

The status code definitions are as follows:

    +----------------------+------------------------------------------------------------+
    | StatusCode           |                                                            |
    +======================+============================================================+
    | 100                  | The command is OK                                          |
    +----------------------+------------------------------------------------------------+
    | 200                  | All the data has been inserted / deleted                   |
    +----------------------+------------------------------------------------------------+
    | 300                  | The insertion / deletion is in progress                    |
    +----------------------+------------------------------------------------------------+
