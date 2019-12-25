"""
    Concurrent segment fetcher.

    @Author jonnykong@cs.ucla.edu
    @Date   2019-10-15
"""

import asyncio as aio
from typing import Optional
from ndn.app import NDNApp
from ndn.types import InterestNack, InterestTimeout
from ndn.encoding import Name, Component, ndn_format_0_3
from datetime import datetime


async def concurrent_fetcher(app: NDNApp, name, start_block_id: Optional[int],
                             end_block_id: Optional[int], semaphore: aio.Semaphore):
    """
    An async-generator to fetch segmented object. Interests are issued concurrently.
    :param app: NDNApp.
    :param name: NonStrictName. Name prefix of Data.
    :return: Yield (data_bytes) tuples in order.
    """
    cur_id = start_block_id if start_block_id is not None else 0
    final_id = end_block_id if end_block_id is not None else 0x7fffffff
    is_failed = False
    tasks = []
    recv_window = cur_id - 1
    seq_to_data_packet = dict()           # Buffer for out-of-order delivery
    received_or_fail = aio.Event()  #

    async def _retry(seq: int):
        """
        Retry 3 times fetching data of the given sequence number or fail.
        :param seq: block_id of data
        """
        nonlocal app, name, semaphore, is_failed, received_or_fail, final_id
        int_name = name[:]
        int_name.append(str(seq))

        trial_times = 0
        while True:
            trial_times += 1
            if trial_times > 3:
                semaphore.release()
                is_failed = True
                received_or_fail.set()
                return
            try:
                print(datetime.now().strftime("%H:%M:%S.%f "), end='')
                print('Express Interest: {}'.format(Name.to_str(int_name)))

                # Get the data name first, and then use the name to get the entire packet value (including sig). This
                # is necessary because express_interest() does not return the sig, which is needed by the repo. An
                # additional decoding step is necessary to obtain the metadata.
                data_name, _, _ = await app.express_interest(
                    int_name, must_be_fresh=True, can_be_prefix=False, lifetime=1000)
                data_bytes = app.get_original_packet_value(data_name)
                (_, meta_info, content, sig) = ndn_format_0_3.parse_data(data_bytes, with_tl=False)

                # Save data and update final_id
                print(datetime.now().strftime("%H:%M:%S.%f "), end='')
                print('Received data: {}'.format(Name.to_str(data_name)))
                seq_to_data_packet[seq] = data_bytes
                if meta_info is not None and meta_info.final_block_id is not None:
                    final_id = Component.to_number(meta_info.final_block_id)
                break
            except InterestNack as e:
                print(f'Nacked with reason={e.reason}')
            except InterestTimeout:
                print(f'Timeout')
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
                recv_window += 1
            return


async def main(app: NDNApp):
    """
    Async helper function to run the concurrent fetcher.
    This function is necessary because it's responsible for calling app.shutdown().
    :param app: NDNApp
    """
    semaphore = aio.Semaphore(20)
    async for data_bytes in concurrent_fetcher(app, Name.from_str('/test1.pdf'), 0, 161, semaphore):
        (data_name, meta_info, content, sig) = ndn_format_0_3.parse_data(data_bytes, with_tl=False)
        print(Name.to_str(data_name))
    app.shutdown()


if __name__ == '__main__':
    app = NDNApp()
    app.run_forever(after_start=main(app))