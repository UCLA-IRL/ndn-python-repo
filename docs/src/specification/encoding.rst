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


The type number assignments are as follows:

    +----------------------+----------------------------+ 
    | type                 | Assigned number (decimal)  |
    +======================+============================+
    | name                 | 7 (same as default)        |
    +----------------------+----------------------------+
    | start_block_id       | 204                        |
    +----------------------+----------------------------+
    | end_block_id         | 205                        |
    +----------------------+----------------------------+ 
    | process_id           | 205                        |
    +----------------------+----------------------------+ 
    | status_code          | 208                        |
    +----------------------+----------------------------+ 
    | insert_num           | 209                        |
    +----------------------+----------------------------+ 
    | delete_num           | 210                        |
    +----------------------+----------------------------+ 