"""
    Repo command encoding.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-11-01
"""

from ndn.encoding import TlvModel, ModelField, NameField, UintField, RepeatedField, BytesField


class RepoTypeNumber:
    START_BLOCK_ID = 204
    END_BLOCK_ID = 205
    PROCESS_ID = 206
    STATUS_CODE = 208
    INSERT_NUM = 209
    DELETE_NUM = 210
    FORWARDING_HINT = 211
    REGISTER_PREFIX = 212
    CHECK_PREFIX = 213

class ForwardingHint(TlvModel):
    name = NameField()

class RegisterPrefix(TlvModel):
    name = NameField()

class CheckPrefix(TlvModel):
    name = NameField()

class RepoCommandParameter(TlvModel):
    name = NameField()
    forwarding_hint = ModelField(RepoTypeNumber.FORWARDING_HINT, ForwardingHint)
    start_block_id = UintField(RepoTypeNumber.START_BLOCK_ID)
    end_block_id = UintField(RepoTypeNumber.END_BLOCK_ID)
    process_id = BytesField(RepoTypeNumber.PROCESS_ID)
    register_prefix = ModelField(RepoTypeNumber.REGISTER_PREFIX, RegisterPrefix)
    check_prefix = ModelField(RepoTypeNumber.CHECK_PREFIX, CheckPrefix)

class RepoCommandResponse(TlvModel):
    name = NameField()
    start_block_id = UintField(RepoTypeNumber.START_BLOCK_ID)
    end_block_id = UintField(RepoTypeNumber.END_BLOCK_ID)
    process_id = BytesField(RepoTypeNumber.PROCESS_ID)
    status_code = UintField(RepoTypeNumber.STATUS_CODE)
    insert_num = UintField(RepoTypeNumber.INSERT_NUM)
    delete_num = UintField(RepoTypeNumber.DELETE_NUM)

class RepeatedNames(TlvModel):
    names = RepeatedField(NameField())
