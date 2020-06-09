"""
    Repo command encoding.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-11-01
"""

from ndn.encoding import TlvModel, NameField, UintField, RepeatedField, ModelField


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
    register_prefix = NameField()


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



#Catalog Parameters

class CatalogCommandParameter(TlvModel):
    """
    Insertion request App Param format.
    """
    name = NameField()
    data_name = NameField()


class CatalogResponseParameter(TlvModel):
    """
    Catalog Response App Param format.
    """
    status = UintField(8)


class CatalogRequestParameter(TlvModel):
    """
    The data mapping fetch request from a client.
    """
    data_name = NameField()


class CatalogInsertParameter(TlvModel):
    """
    A single Insert Parameter format containing the data name, the name to map and the expiry time.
    """
    data_name = NameField()
    name = NameField()
    expire_time_ms = UintField(2)


class CatalogDeleteParameter(TlvModel):
    """
    A single Delete Parameter format containing the data name and the name mapped to be deleted.
    """
    data_name = NameField()
    name = NameField()


class CatalogDataListParameter(TlvModel):
    """
    The complete insertion request data format. Contains list of insertion and deletion parameters.
    """
    insert_data_names = RepeatedField(ModelField(1, CatalogInsertParameter))
    delete_data_names = RepeatedField(ModelField(2, CatalogDeleteParameter))

    
class CatalogDataFetchParameter(TlvModel):
    data_name = NameField()