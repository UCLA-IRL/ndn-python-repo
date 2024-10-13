# -----------------------------------------------------------------------------
# Concurrent segment fetcher.
#
# @Author jonnykong@cs.ucla.edu tianyuan@cs.ucla.edu
# @Date   2024-05-24
# -----------------------------------------------------------------------------

import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.types import InterestNack, InterestTimeout, InterestCanceled
from ndn.encoding import Name, NonStrictName, Component
from typing import Optional

class IdNamingConv:
    SEGMENT = 1
    SEQUENCE = 2
    NUMBER = 3

async def concurrent_fetcher(app: NDNApp, name: NonStrictName, start_id: int,
                             end_id: Optional[int], semaphore: aio.Semaphore, **kwargs):
    """
    An async-generator to fetch data packets between "`name`/`start_id`" and "`name`/`end_id`"\
        concurrently.

    :param app: NDNApp.
    :param name: NonStrictName. Name prefix of Data.
    :param start_id: int. The start number.
    :param end_id: Optional[int]. The end segment number. If not specified, continue fetching\
        until an interest receives timeout or nack or 3 times.
    :param semaphore: aio.Semaphore. Semaphore used to fetch data.
    :return: Yield ``(FormalName, MetaInfo, Content, RawPacket)`` tuples in order.
    """
    name_conv = IdNamingConv.SEGMENT
    max_retries = 15
    if 'name_conv' in kwargs:
        name_conv = kwargs['name_conv']
    if 'max_retries' in kwargs:
        max_retries = kwargs['max_retries']
    cur_id = start_id
    final_id = end_id if end_id is not None else 0x7fffffff
    is_failed = False
    tasks = []
    recv_window = cur_id - 1
    seq_to_data_packet = dict()           # Buffer for out-of-order delivery
    received_or_fail = aio.Event()
    name = Name.normalize(name)
    logger = logging.getLogger(__name__)

    async def _retry(seq: int):
        """
        Retry 3 times fetching data of the given sequence number or fail.
        :param seq: block_id of data
        """
        nonlocal app, name, semaphore, is_failed, received_or_fail, final_id
        if name_conv == IdNamingConv.SEGMENT:
            int_name = name + [Component.from_segment(seq)]
        elif name_conv == IdNamingConv.SEQUENCE:
            int_name = name + [Component.from_sequence_num(seq)]
        elif name_conv == IdNamingConv.NUMBER:
            # fixme: .from_number apparently requires a second parameter for "type"
            int_name = name + [Component.from_number(seq)]
        else:
            logging.error('Unrecognized naming convention')
            return
        trial_times = 0
        while True:
            trial_times += 1
            # always retry when max_retries is -1
            if 0 <= max_retries < trial_times:
                semaphore.release()
                is_failed = True
                received_or_fail.set()
                return
            try:
                logger.info('Express Interest: {}'.format(Name.to_str(int_name)))
                data_name, meta_info, content, data_bytes = await app.express_interest(
                    int_name, need_raw_packet=True, can_be_prefix=False, lifetime=1000, **kwargs)

                # Save data and update final_id
                logging.info('Received data: {}'.format(Name.to_str(data_name)))
                if name_conv == IdNamingConv.SEGMENT and \
                    meta_info is not None and \
                    meta_info.final_block_id is not None:
                    # we need to change final block id before yielding packets,
                    # preventing window moving beyond the final block id
                    final_id = Component.to_number(meta_info.final_block_id)

                    # cancel the Interests for non-existing data
                    for task in aio.all_tasks():
                        task_name = task.get_name()
                        try:
                            task_num = int(task_name)
                        except:
                            continue
                        if task_num and task_num > final_id \
                            and task in tasks:
                            tasks.remove(task)
                            task.cancel()
                seq_to_data_packet[seq] = (data_name, meta_info, content, data_bytes)
                break
            except InterestNack as e:
                logging.info(f'Interest {Name.to_str(int_name)} nacked with reason={e.reason}')
            except InterestTimeout:
                logging.info(f'Interest {Name.to_str(int_name)} timeout')
            except InterestCanceled:
                logging.info(f'Interest {Name.to_str(int_name)} (might legally) cancelled')
                return
        semaphore.release()
        received_or_fail.set()

    async def _dispatch_tasks():
        """
        Dispatch retry() tasks using semaphore.
        """
        nonlocal semaphore, tasks, cur_id, final_id, is_failed
        while cur_id <= final_id:
            await semaphore.acquire()
            # in case final_id has been updated while waiting semaphore
            # typically happened after the first round trip when we update 
            # the actual final_id with the final block id obtained from data.
            if cur_id > final_id:
                # giving back the semaphore
                semaphore.release()
                break
            if is_failed:
                received_or_fail.set()
                semaphore.release()
                break
            task = aio.get_event_loop().create_task(_retry(cur_id))
            task.set_name(cur_id)
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
            # TODO: complete misuse of async for & yield. The generator does not make any sense since
            # all data are already fetched.
            while recv_window + 1 in seq_to_data_packet:
                yield seq_to_data_packet[recv_window + 1]
                del seq_to_data_packet[recv_window + 1]
                recv_window += 1
            return
