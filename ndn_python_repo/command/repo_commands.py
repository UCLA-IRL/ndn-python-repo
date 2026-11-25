"""
    Repo command encoding.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-11-01
"""

import dataclasses as dc
import ndn.encoding as enc

__all__ = [
    "RepoTypeNumber",
    "EmbName",
    "ObjParam",
    "SyncParam",
    "SyncStatus",
    "RepoCommandParam",
    "ObjStatus",
    "RepoCommandRes",
    "RepeatedNames",
    "RepoStatCode",
    "RepoStatQuery",
]


class RepoTypeNumber:
    START_BLOCK_ID = 204
    END_BLOCK_ID = 205
    REQUEST_NO = 206
    STATUS_CODE = 208
    INSERT_NUM = 209
    DELETE_NUM = 210
    FORWARDING_HINT = 211
    REGISTER_PREFIX = 212
    CHECK_PREFIX = 213
    OBJECT_PARAM = 301
    OBJECT_RESULT = 302
    SYNC_PARAM = 401
    SYNC_RESULT = 402
    SYNC_DATA_NAME_DEDUPE = 403
    SYNC_RESET = 404
    SYNC_PREFIX = 405


class RepoStatCode:
    # 100 has not been used by previous code, but defined and documented.
    # The current code use it for acknowledged but not started yet.
    ROGER = 100
    # All data have been inserted / deleted
    COMPLETED = 200
    # Work in progress
    IN_PROGRESS = 300
    # Some data failed to be inserted / deleted
    FAILED = 400
    # The command or param is malformed
    MALFORMED = 403
    # The queried operation cannot be found
    NOT_FOUND = 404


@dc.dataclass
class EmbName:
    name: enc.NDNName = enc.tlv_field(enc.Name.TYPE_NAME, default=None)

    @staticmethod
    def from_name(name: enc.NonStrictName) -> 'EmbName':
        return EmbName(name=name)


@dc.dataclass
class ObjParam:
    name: enc.NDNName = enc.tlv_field(enc.Name.TYPE_NAME, default=None)
    forwarding_hint: enc.Links | None = enc.tlv_field(RepoTypeNumber.FORWARDING_HINT, default=None)
    start_block_id: int | None = enc.tlv_field(RepoTypeNumber.START_BLOCK_ID, default=None)
    end_block_id: int | None = enc.tlv_field(RepoTypeNumber.END_BLOCK_ID, default=None)
    register_prefix: EmbName | None = enc.tlv_field(RepoTypeNumber.REGISTER_PREFIX, default=None)


@dc.dataclass
class SyncParam:
    sync_prefix: EmbName | None = enc.tlv_field(RepoTypeNumber.SYNC_PREFIX, default=None)
    register_prefix: EmbName | None = enc.tlv_field(RepoTypeNumber.REGISTER_PREFIX, default=None)
    data_name_dedupe: bool = enc.tlv_field(RepoTypeNumber.SYNC_DATA_NAME_DEDUPE, default=False)
    reset: bool = enc.tlv_field(RepoTypeNumber.SYNC_RESET, default=False)


@dc.dataclass
class RepoCommandParam:
    objs: list[ObjParam] = enc.tlv_field(RepoTypeNumber.OBJECT_PARAM, default_factory=list)
    sync_groups: list[SyncParam] = enc.tlv_field(RepoTypeNumber.SYNC_PARAM, default_factory=list)


@dc.dataclass
class RepoStatQuery:
    request_no: bytes | None = enc.tlv_field(RepoTypeNumber.REQUEST_NO, default=None)


@dc.dataclass
class ObjStatus:
    name: enc.NDNName = enc.tlv_field(enc.Name.TYPE_NAME, default=None)
    status_code: int | None = enc.tlv_field(RepoTypeNumber.STATUS_CODE, default=None)
    insert_num: int | None = enc.tlv_field(RepoTypeNumber.INSERT_NUM, default=None)
    delete_num: int | None = enc.tlv_field(RepoTypeNumber.DELETE_NUM, default=None)


@dc.dataclass
class SyncStatus:
    name: enc.NDNName = enc.tlv_field(enc.Name.TYPE_NAME, default=None)
    status_code: int | None = enc.tlv_field(RepoTypeNumber.STATUS_CODE, default=None)


@dc.dataclass
class RepoCommandRes:
    status_code: int | None = enc.tlv_field(RepoTypeNumber.STATUS_CODE, default=None)
    objs: list[ObjStatus] = enc.tlv_field(RepoTypeNumber.OBJECT_RESULT, default_factory=list)
    sync_groups: list[SyncStatus] = enc.tlv_field(RepoTypeNumber.SYNC_RESULT, default_factory=list)


@dc.dataclass
class RepeatedNames:
    names: list[enc.NDNName] = enc.tlv_field(enc.Name.TYPE_NAME, default_factory=list)
