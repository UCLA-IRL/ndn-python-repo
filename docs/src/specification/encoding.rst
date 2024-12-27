Encoding
========

Most repo commands and status reports are Data packets whose Content contains
``RepoCommandParam`` or ``RepoCommandRes`` structure.
These Data are issued via Pub-Sub protocol.
Each ``RepoCommandParam`` and ``RepoCommandRes`` contains
multiple ``ObjParam`` and ``ObjStatus``, resp.

Current protocol does not support compatibility among different versions. All TLV-TYPE numbers are critical.

These structures are defined as follows:

.. code-block:: abnf

    ObjParam =
        Name
        [ForwardingHint]
        [StartBlockId]
        [EndBlockId]
        [RegisterPrefix]

    SyncParam =
        SyncPrefix
        [RegisterPrefix]
        [DataNameDedupe]
        [Reset]

    ObjStatus =
        Name
        StatusCode
        [InsertNum]
        [DeleteNum]

    SyncStatus =
        Name
        StatusCode

    RepoCommandParam =
        0* (OBJECT-PARAM-TYPE TLV-LENGTH ObjParam)
        0* (SYNC-PARAM-TYPE TLV-LENGTH SyncParam)

    RepoCommandRes =
        StatusCode
        0* (OBJECT-RESULT-TYPE TLV-LENGTH ObjStatus)
        0* (SYNC-RESULT-TYPE TLV-LENGTH SyncStatus)

    RepoStatQuery =
        RequestNo

    ForwardingHint = FORWARDING-HINT-TYPE TLV-LENGTH Name

    StartBlockId = START-BLOCK-ID-TYPE TLV-LENGTH NonNegativeInteger

    EndBlockId = END-BLOCK-ID-TYPE TLV-LENGTH NonNegativeInteger

    RegisterPrefix = REGISTER-PREFIX-TYPE TLV-LENGTH Name

    SyncPrefix = SYNC-PREFIX-TYPE TLV-LENGTH Name

    DataNameDedupe = SYNC-DATA-NAME-DEDUPE-TYPE TLV-LENGTH ; TLV-LENGTH = 0

    Reset = SYNC-RESET-TYPE TLV-LENGTH ; TLV-LENGTH = 0

    StatusCode = STATUS-CODE-TYPE TLV-LENGTH NonNegativeInteger

    InsertNum = INSERT-NUM-TYPE TLV-LENGTH NonNegativeInteger

    DeleteNum = DELETE-NUM-TYPE TLV-LENGTH NonNegativeInteger

    RequestNo = REQUEST-NO-TYPE TLV-LENGTH 1*OCTET

The type number assignments are as follows:

    +----------------------------+----------------------------+--------------------------------+
    | type                       | Assigned number (decimal)  | Assigned number (hexadecimal)  |
    +============================+============================+================================+
    | START-BLOCK-ID-TYPE        | 204                        | 0xCC                           |
    +----------------------------+----------------------------+--------------------------------+
    | END-BLOCK-ID-TYPE          | 205                        | 0xCD                           |
    +----------------------------+----------------------------+--------------------------------+
    | REQUEST-NO-TYPE            | 206                        | 0xCE                           |
    +----------------------------+----------------------------+--------------------------------+
    | STATUS-CODE-TYPE           | 208                        | 0xD0                           |
    +----------------------------+----------------------------+--------------------------------+
    | INSERT-NUM-TYPE            | 209                        | 0xD1                           |
    +----------------------------+----------------------------+--------------------------------+
    | DELETE-NUM-TYPE            | 210                        | 0xD2                           |
    +----------------------------+----------------------------+--------------------------------+
    | FORWARDING-HINT-TYPE       | 211                        | 0xD3                           |
    +----------------------------+----------------------------+--------------------------------+
    | REGISTER-PREFIX-TYPE       | 212                        | 0xD4                           |
    +----------------------------+----------------------------+--------------------------------+
    | OBJECT-PARAM-TYPE          | 301                        | 0x12D                          |
    +----------------------------+----------------------------+--------------------------------+
    | OBJECT-RESULT-TYPE         | 302                        | 0x12E                          |
    +----------------------------+----------------------------+--------------------------------+
    | SYNC-PARAM-TYPE            | 401                        | 0x191                          |
    +----------------------------+----------------------------+--------------------------------+
    | SYNC-RESULT-TYPE           | 402                        | 0x192                          |
    +----------------------------+----------------------------+--------------------------------+
    | SYNC-DATA-NAME-DEDUPE-TYPE | 403                        | 0x193                          |
    +----------------------------+----------------------------+--------------------------------+
    | SYNC-RESET-TYPE            | 404                        | 0x194                          |
    +----------------------------+----------------------------+--------------------------------+
    | SYNC-PREFIX-TYPE           | 405                        | 0x195                          |
    +----------------------------+----------------------------+--------------------------------+


Status Code Definition
----------------------

The status codes are defined as follows:

    +---------------+-------+-----------------------------------------------+
    | Code name     | Value | Explanation                                   |
    +===============+=======+===============================================+
    | ROGER         | 100   | Command received but not been executed yet    |
    +---------------+-------+-----------------------------------------------+
    | COMPLETED     | 200   | Command completed                             |
    +---------------+-------+-----------------------------------------------+
    | IN-PROGRESS   | 300   | Command working in progress                   |
    +---------------+-------+-----------------------------------------------+
    | FAILED        | 400   | Command or parts of it failed                 |
    +---------------+-------+-----------------------------------------------+
    | MALFORMED     | 403   | Command is malformed                          |
    +---------------+-------+-----------------------------------------------+
    | NOT-FOUND     | 404   | Queried command not found                     |
    +---------------+-------+-----------------------------------------------+
