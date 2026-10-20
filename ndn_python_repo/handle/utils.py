import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import NonStrictName
from ndn.types import InterestNack, InterestTimeout
from typing import Optional
from ..command import ObjParam, RepoStatCode
from ..storage import Storage
from ..utils import concurrent_fetcher


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


async def fetch_object(app: NDNApp, storage: Storage, obj: ObjParam) -> tuple[RepoStatCode, int]:
    """
    Fetch and store the Data packets requested by one object of an insert or ingest command.
    :param app: NDNApp.
    :param storage: Storage.
    :param obj: The object to fetch.
    :return: (status code, number of data packets stored). The status code is MALFORMED if obj
        is invalid, COMPLETED if all requested data packets are stored, and FAILED otherwise.
    """
    valid, start_block_id, end_block_id = normalize_block_ids(obj)
    if not obj.name or not valid:
        return RepoStatCode.MALFORMED, 0

    if obj.forwarding_hint and obj.forwarding_hint.names:
        forwarding_hint = obj.forwarding_hint.names
    else:
        forwarding_hint = None

    if start_block_id is not None:
        # Fetch data packets with block ids appended to the end
        insert_num = await fetch_segmented_data(app, storage, obj.name, start_block_id, end_block_id,
                                                forwarding_hint)
        if end_block_id is None:
            # end_block_id is auto detected, at least one data packet must be fetched
            is_success = insert_num > 0
        else:
            is_success = start_block_id + insert_num - 1 == end_block_id
    else:
        # Both start_block_id and end_block_id are None, fetch a single data packet
        insert_num = await fetch_single_data(app, storage, obj.name, forwarding_hint)
        is_success = insert_num == 1

    return (RepoStatCode.COMPLETED if is_success else RepoStatCode.FAILED), insert_num


async def fetch_single_data(app: NDNApp, storage: Storage, name: NonStrictName,
                            forwarding_hint: Optional[list[NonStrictName]]):
    """
    Fetch one Data packet.
    :param app: NDNApp.
    :param storage: Storage.
    :param name: NonStrictName.
    :param forwarding_hint: Optional[list[NonStrictName]]
    :return:  Number of data packets fetched.
    """
    n_retries = 3
    while n_retries > 0:
        try:
            data_name, _, _, data_bytes = await app.express_interest(
                name, need_raw_packet=True, can_be_prefix=False, lifetime=2000,
                forwarding_hint=forwarding_hint)
            storage.put_data_packet(data_name, data_bytes)
            return 1
        except InterestNack as e:
            logging.info(f'Nacked with reason={e.reason}')
            await aio.sleep(1)
            n_retries -= 1
        except InterestTimeout:
            logging.info(f'Timeout')
            n_retries -= 1
    return 0


async def fetch_segmented_data(app: NDNApp, storage: Storage, name: NonStrictName, start_block_id: int,
                               end_block_id: Optional[int], forwarding_hint: Optional[list[NonStrictName]]):
    """
    Fetch segmented Data packets.
    :param app: NDNApp.
    :param storage: Storage.
    :param name: NonStrictName.
    :param start_block_id: int
    :param end_block_id: Optional[int]
    :param forwarding_hint: Optional[list[NonStrictName]]
    :return: Number of data packets fetched.
    """
    semaphore = aio.Semaphore(10)
    block_id = start_block_id
    async for (data_name, _, _, data_bytes) in (
            concurrent_fetcher(app, name, start_block_id, end_block_id,
                               semaphore, forwarding_hint=forwarding_hint)):
        storage.put_data_packet(data_name, data_bytes)
        block_id += 1
    insert_num = block_id - start_block_id
    return insert_num
