# -----------------------------------------------------------------------------
# Concurrent segment fetcher.
#
# @Author jonnykong@cs.ucla.edu
# @Date   2019-10-15
# -----------------------------------------------------------------------------

import asyncio as aio
from datetime import datetime
import logging
from ndn.app import NDNApp
from ndn.types import InterestNack, InterestTimeout
from ndn.encoding import Name, NonStrictName, Component
from typing import Optional


async def concurrent_fetcher(app: NDNApp, name: NonStrictName, start_block_id: int,
                             end_block_id: Optional[int], semaphore: aio.Semaphore, **kwargs):
    """
    An async-generator to fetch data packets between "`name`/`start_block_id`" and "`name`/`end_block_id`"\
        concurrently.

    :param app: NDNApp.
    :param name: NonStrictName. Name prefix of Data.
    :param start_block_id: int. The start segment number.
    :param end_block_id: Optional[int]. The end segment number. If not specified, continue fetching\
        until an interest receives timeout or nack or 3 times.
    :return: Yield ``(FormalName, MetaInfo, Content, RawPacket)`` tuples in order.
    """
    cur_id = start_block_id
    final_id = end_block_id if end_block_id is not None else 0x7fffffff
    is_failed = False
    tasks = []
    recv_window = cur_id - 1
    seq_to_data_packet = dict()           # Buffer for out-of-order delivery
    received_or_fail = aio.Event()

    async def _retry(seq: int):
        """
        Retry 3 times fetching data of the given sequence number or fail.
        :param seq: block_id of data
        """
        nonlocal app, name, semaphore, is_failed, received_or_fail, final_id
        int_name = name + [Component.from_segment(seq)]

        trial_times = 0
        while True:
            trial_times += 1
            if trial_times > 3:
                semaphore.release()
                is_failed = True
                received_or_fail.set()
                return
            try:
                logging.info('Express Interest: {}'.format(Name.to_str(int_name)))
                data_name, meta_info, content, data_bytes = await app.express_interest(
                    int_name, need_raw_packet=True, can_be_prefix=False, lifetime=1000, **kwargs)

                # Save data and update final_id
                logging.info('Received data: {}'.format(Name.to_str(data_name)))
                seq_to_data_packet[seq] = (data_name, meta_info, content, data_bytes)
                if meta_info is not None and meta_info.final_block_id is not None:
                    final_id = Component.to_number(meta_info.final_block_id)
                break
            except InterestNack as e:
                logging.info(f'Nacked with reason={e.reason}')
            except InterestTimeout:
                logging.info(f'Timeout')
        semaphore.release()
        received_or_fail.set()

    async def _dispatch_tasks():
        """
        Dispatch retry() tasks using semaphore.
        """
        nonlocal semaphore, tasks, cur_id, final_id, is_failed
        while cur_id <= final_id:
            await semaphore.acquire()
            if is_failed:
                received_or_fail.set()
                semaphore.release()
                break
            task = aio.get_event_loop().create_task(_retry(cur_id))
            tasks.append(task)
            cur_id += 1

    aio.get_event_loop().create_task(_dispatch_tasks())
    while True:
        await received_or_fail.wait()
        received_or_fail.clear()
        # Re-assemble bytes in order
        while recv_window + 1 in seq_to_data_packet:
            yield seq_to_data_packet[recv_window + 1]
            del seq_to_data_packet[recv_window + 1]
            recv_window += 1
        # Return if all data have been fetched, or the fetching process failed
        if recv_window == final_id:
            await aio.gather(*tasks)
            return
        elif is_failed:
            await aio.gather(*tasks)
            # New data may return during gather(), need to check again
            while recv_window + 1 in seq_to_data_packet:
                yield seq_to_data_packet[recv_window + 1]
                del seq_to_data_packet[recv_window + 1]
                recv_window += 1
            return
