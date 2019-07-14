import asyncio
import threading
import logging
from typing import Union, Optional, Callable
from pyndn import Face, Interest, NetworkNack, Data, Name


async def fetch_data_packet(face: Face, interest: Interest) -> Union[Data, NetworkNack, None]:
    done = threading.Event()
    result = None

    def on_data(_interest, data: Data):
        nonlocal done, result
        result = data
        done.set()

    def on_timeout(_interest):
        nonlocal done
        done.set()

    def on_network_nack(_interest, network_nack: NetworkNack):
        nonlocal done, result
        result = network_nack
        done.set()

    async def wait_for_event():
        ret = False
        while not ret:
            ret = done.wait(0.01)
            await asyncio.sleep(0.01)

    try:
        face.expressInterest(interest, on_data, on_timeout, on_network_nack)
        print('Express interest: {}'.format(interest.getName()))
        await wait_for_event()
        return result
    except (ConnectionRefusedError, BrokenPipeError) as error:
        return error


async def fetch_segmented_data(face: Face, prefix: Name, start_block_id: Optional[int],
                               end_block_id: Optional[int], semaphore: asyncio.Semaphore,
                               after_fetched: Callable):
    """
    Fetch segmented data from start_block_id or 0, to end_block_id or FinalBlockId returned
    in data, whichever is smaller. Call after_fetched upon receiving every data.
    Maintain a fixed size window using semaphore.
    TODO: Remove hard-coded part
    TODO: Break when some n_fail reaches a threshold
    """
    FETCHER_RETRY_INTERVAL = 1
    FETCHER_MAX_ATTEMPT_NUMBER = 3

    async def retry_or_fail(interest: Interest):
        """
        Retry for up to FETCHER_MAX_ATTEMPT_NUMBER times, and write to storage
        """
        nonlocal n_success, n_fail, cur_id, final_id

        logging.info('retry_or_fail(): {}'.format(interest.getName()))

        for _ in range(FETCHER_MAX_ATTEMPT_NUMBER):
            response = await fetch_data_packet(face, interest)
            success = False
            if isinstance(response, Data):
                final_id_component = response.metaInfo.getFinalBlockId()
                if final_id_component.isSegment():
                    final_id = final_id_component.toSegment()
                success = True
                break
            else:
                await asyncio.sleep(FETCHER_RETRY_INTERVAL / 1000.0)
        if success:
            n_success += 1
        else:
            n_fail += 1
        if n_success + n_fail >= final_id - start_block_id + 1:
            done.set()

        semaphore.release()
        after_fetched(response)

    cur_id = (start_block_id if start_block_id else 0)
    final_id = (end_block_id if end_block_id else 0x7fffffff)
    n_success = 0
    n_fail = 0
    event_loop = asyncio.get_event_loop()
    done = asyncio.Event()

    # Need to acquire semaphore before adding task to event loop, otherwise an unlimited
    # number of tasks would be added
    while cur_id <= final_id:
        await semaphore.acquire()
        interest = Interest(Name(prefix).appendSegment(cur_id))
        event_loop.create_task(retry_or_fail(interest))
        cur_id += 1
    await done.wait()

    return n_success

