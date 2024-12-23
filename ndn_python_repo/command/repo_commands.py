"""
    Repo command encoding.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-11-01
"""

from typing import TypeVar
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


TEmbName = TypeVar('TEmbName', bound='EmbName')


class EmbName(enc.TlvModel):
    name = enc.NameField()

    @staticmethod
    def from_name(name: enc.NonStrictName) -> TEmbName:
        ret = EmbName()
        ret.name = name
        return ret


class ObjParam(enc.TlvModel):
    name = enc.NameField()
    forwarding_hint = enc.ModelField(RepoTypeNumber.FORWARDING_HINT, enc.Links)
    start_block_id = enc.UintField(RepoTypeNumber.START_BLOCK_ID)
    end_block_id = enc.UintField(RepoTypeNumber.END_BLOCK_ID)
    register_prefix = enc.ModelField(RepoTypeNumber.REGISTER_PREFIX, EmbName)


class SyncParam(enc.TlvModel):
    sync_prefix = enc.ModelField(RepoTypeNumber.SYNC_PREFIX, EmbName)
    register_prefix = enc.ModelField(RepoTypeNumber.REGISTER_PREFIX, EmbName)
    data_name_dedupe = enc.BoolField(RepoTypeNumber.SYNC_DATA_NAME_DEDUPE)
    reset = enc.BoolField(RepoTypeNumber.SYNC_RESET)
    # forwarding_hint = enc.ModelField(RepoTypeNumber.FORWARDING_HINT, enc.Links)
    # sync_prefix = enc.ModelField(RepoTypeNumber.REGISTER_PREFIX, EmbName)


class RepoCommandParam(enc.TlvModel):
    objs = enc.RepeatedField(enc.ModelField(RepoTypeNumber.OBJECT_PARAM, ObjParam))
    sync_groups = enc.RepeatedField(
        enc.ModelField(RepoTypeNumber.SYNC_PARAM, SyncParam)
    )


class RepoStatQuery(enc.TlvModel):
    request_no = enc.BytesField(RepoTypeNumber.REQUEST_NO)


class ObjStatus(enc.TlvModel):
    name = enc.NameField()
    status_code = enc.UintField(RepoTypeNumber.STATUS_CODE)
    insert_num = enc.UintField(RepoTypeNumber.INSERT_NUM)
    delete_num = enc.UintField(RepoTypeNumber.DELETE_NUM)


class SyncStatus(enc.TlvModel):
    name = enc.NameField()
    status_code = enc.UintField(RepoTypeNumber.STATUS_CODE)


class RepoCommandRes(enc.TlvModel):
    status_code = enc.UintField(RepoTypeNumber.STATUS_CODE)
    objs = enc.RepeatedField(enc.ModelField(RepoTypeNumber.OBJECT_RESULT, ObjStatus))
    sync_groups = enc.RepeatedField(
        enc.ModelField(RepoTypeNumber.SYNC_RESULT, SyncStatus)
    )


class RepeatedNames(enc.TlvModel):
    names = enc.RepeatedField(enc.NameField())
