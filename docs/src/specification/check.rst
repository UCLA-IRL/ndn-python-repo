.. _specification-check-label:

Check
=====

The check protocols is used by the clients to check the status of a 
insertion or deletion process.

1. After the repo receives the insert/delete command, it periodically publishes the status of the corresponding process to topic ``/<check_prefix>/check/<process_id>``. The published message is a ``RepoCommandResponse`` encoded in TLV format. Here, ``check_prefix`` and ``process_id`` are obtained from the insert/delete command.

2. The application can subscribe to the corresponding topic, to get the process's status.
