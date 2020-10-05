Encoding
========

Most repo commands and status reports are Data packets whose Content contains
``RepoCommandParameter`` or ``RepoCommandResponse`` structure.
These structures are defined as follows:

.. code-block:: abnf

    RepoCommandParameter =
        [Name]
        [ForwardingHint]
        [StartBlockId]
        [EndBlockId]
        [ProcessId]
        [RegisterPrefix]
        [CheckPrefix]

    RepoCommandResponse =
        [Name]
        [StartBlockId]
        [EndBlockId]
        [ProcessId]
        [StatusCode]
        [InsertNum]
        [DeleteNum]

    ForwardingHint = FORWARDING-HINT-TYPE TLV-LENGTH Name

    StartBlockId = START-BLOCK-ID-TYPE TLV-LENGTH NonNegativeInteger

    EndBlockId = END-BLOCK-ID-TYPE TLV-LENGTH NonNegativeInteger

    ProcessId = PROCESS-ID-TYPE TLV-LENGTH NonNegativeInteger

    RegisterPrefix = REGISTER-PREFIX-TYPE TLV-LENGTH Name

    CheckPrefix = CHECK-PREFIX-TYPE TLV-LENGTH Name

    StatusCode = STATUS-CODE-TYPE TLV-LENGTH NonNegativeInteger

    InsertNum = INSERT-NUM-TYPE TLV-LENGTH NonNegativeInteger

    DeleteNum = DELETE-NUM-TYPE TLV-LENGTH NonNegativeInteger

The type number assignments are as follows:

    +----------------------+----------------------------+--------------------------------+
    | type                 | Assigned number (decimal)  | Assigned number (hexadecimal)  |
    +======================+============================+================================+
    | START-BLOCK-ID-TYPE  | 204                        | 0xCC                           |
    +----------------------+----------------------------+--------------------------------+
    | END-BLOCK-ID-TYPE    | 205                        | 0xCD                           |
    +----------------------+----------------------------+--------------------------------+
    | PROCESS-ID-TYPE      | 206                        | 0xCE                           |
    +----------------------+----------------------------+--------------------------------+
    | STATUS-CODE-TYPE     | 208                        | 0xD0                           |
    +----------------------+----------------------------+--------------------------------+
    | INSERT-NUM-TYPE      | 209                        | 0xD1                           |
    +----------------------+----------------------------+--------------------------------+
    | DELETE-NUM-TYPE      | 210                        | 0xD2                           |
    +----------------------+----------------------------+--------------------------------+
    | FORWARDING-HINT-TYPE | 211                        | 0xD3                           |
    +----------------------+----------------------------+--------------------------------+
    | REGISTER-PREFIX-TYPE | 212                        | 0xD4                           |
    +----------------------+----------------------------+--------------------------------+
    | CHECK-PREFIX-TYPE    | 213                        | 0xD5                           |
    +----------------------+----------------------------+--------------------------------+
