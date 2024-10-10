from typing import Optional
from ..command import ObjParam


def normalize_block_ids(obj: ObjParam) -> tuple[bool, Optional[int], Optional[int]]:
    """
    Normalize insert parameter, or reject the param if it's invalid.
    :param obj: The object to fetch.
    :return: Returns (true, start id, end id) if cmd_param is valid.
    """
    start_id = obj.start_block_id
    end_id = obj.end_block_id

    # Valid if neither start_block_id nor end_block_id is given, fetch single data without seg number
    if start_id is None and end_id is None:
        return True, None, None

    # If start_block_id is not given, it is set to 0
    if start_id is None:
        start_id = 0

    # Valid if end_block_id is not given, attempt to fetch all segments until receiving timeout
    # Valid if end_block_id is given, and larger than or equal to start_block_id
    if end_id is None or end_id >= start_id:
        return True, start_id, end_id

    return False, None, None
