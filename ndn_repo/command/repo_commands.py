"""
    Repo command encoding.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-11-01
"""

from ndn.encoding import TlvModel, NameField, UintField, RepeatedField


class RepoTypeNumber:
    START_BLOCK_ID = 204
    END_BLOCK_ID = 205
    PROCESS_ID = 206
    STATUS_CODE = 208
    INSERT_NUM = 209
    DELETE_NUM = 210


class RepoCommandParameter(TlvModel):
    name = NameField()
    start_block_id = UintField(RepoTypeNumber.START_BLOCK_ID)
    end_block_id = UintField(RepoTypeNumber.END_BLOCK_ID)
    process_id = UintField(RepoTypeNumber.PROCESS_ID)


class RepoCommandResponse(TlvModel):
    name = NameField()
    start_block_id = UintField(RepoTypeNumber.START_BLOCK_ID)
    end_block_id = UintField(RepoTypeNumber.END_BLOCK_ID)
    process_id = UintField(RepoTypeNumber.PROCESS_ID)
    status_code = UintField(RepoTypeNumber.STATUS_CODE)
    insert_num = UintField(RepoTypeNumber.INSERT_NUM)
    delete_num = UintField(RepoTypeNumber.DELETE_NUM)


class PrefixesInStorage(TlvModel):
    prefixes = RepeatedField(NameField())