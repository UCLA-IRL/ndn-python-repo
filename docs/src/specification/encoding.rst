Encoding
========

The repo commands and responses contains ``RepoCommandParameter`` and
``RepoCommandResponse``, which are custom TLV formats, specifically:

.. code-block::

    RepoCommandParameter = DATA-TYPE TLV-LENGTH
        [name]
        [start_block_id]
        [end_block_id]
        [process_id]
        [register_prefix]

    RepoCommandResponse = DATA-TYPE TLV-LENGTH
        [name]
        [start_block_id]
        [end_block_id]
        [process_id]
        [status_code]
        [insert_num]
        [delete_num]

    name = Name

    start_block_id = START-BLOCK-ID-TYPE TLV-LENGTH NonNegativeInteger

    end_block_id = END-BLOCK-ID-TYPE TLV-LENGTH NonNegativeInteger

    process_id = PROCESS-ID-TYPE TLV-LENGTH NonNegativeInteger

    register_prefix = Name

    status_code = STATUS-CODE-TYPE TLV-LENGTH NonNegativeInteger

    insert_num = INSERT-NUM-TYPE TLV-LENGTH NonNegativeInteger

    delete_num = DELETE-NUM-TYPE TLV-LENGTH NonNegativeInteger

The type number assignments are as follows:

    +----------------------+----------------------------+--------------------------------+
    | type                 | Assigned number (decimal)  | Assigned number (hexadecimal)  |
    +======================+============================+================================+
    | name                 | 7 (same as default)        | 0x07                           |
    +----------------------+----------------------------+--------------------------------+
    | start_block_id       | 204                        | 0xCC                           |
    +----------------------+----------------------------+--------------------------------+
    | end_block_id         | 205                        | 0xCD                           |
    +----------------------+----------------------------+--------------------------------+
    | process_id           | 206                        | 0xCE                           |
    +----------------------+----------------------------+--------------------------------+
    | status_code          | 208                        | 0xD0                           |
    +----------------------+----------------------------+--------------------------------+
    | insert_num           | 209                        | 0xD1                           |
    +----------------------+----------------------------+--------------------------------+
    | delete_num           | 210                        | 0xD2                           |
    +----------------------+----------------------------+--------------------------------+
