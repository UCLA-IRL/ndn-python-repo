import asyncio
import logging
from typing import Union, Optional, Callable
from pyndn import Face, Interest, NetworkNack, Data, Name


async def fetch_data_packet(face: Face, interest: Interest) -> Union[Data, NetworkNack, None]:
    done = asyncio.Event()
    result = None

    def on_data(_interest, data: Data):
        nonlocal done, result
        logging.info('on data')
        result = data
        done.set()

    def on_timeout(_interest):
        nonlocal done
        logging.info('timeout')
        done.set()

    def on_network_nack(_interest, network_nack: NetworkNack):
        nonlocal done, result
        logging.info('nack')
        result = network_nack
        done.set()

    try:
        face.expressInterest(interest, on_data, on_timeout, on_network_nack)
        await done.wait()
        return result
    except (ConnectionRefusedError, BrokenPipeError) as error:
        return error


async def fetch_segmented_data(face: Face, prefix: Name, start_block_id: Optional[int],
                               end_block_id: Optional[int], semaphore: asyncio.Semaphore,
                               after_fetched: Callable):
    """
    Fetch segmented data starting from start_block_id. 
    If start_block_id is not set, start from sequence 0.
    If end_block_id is set, or a data packet returns FinalBlockId, the function will fetch all data
    until that id. Otherwise, it will return until number of failures reach a threshold.
    Upon receiving each data, call after_fetched upon().
    TODO: Remove hard-coded part
    """
    FETCHER_RETRY_INTERVAL = 1
    FETCHER_MAX_ATTEMPT_NUMBER = 3
    FETCHER_FAIL_EXIT_THRESHOLD = 5

    async def retry_or_fail(interest: Interest):
        """
        Retry for up to FETCHER_MAX_ATTEMPT_NUMBER times, and write to storage.
        """
        nonlocal n_success, n_fail, cur_id, final_id
        
        # Need to check sequence number, in case this task was added to the event queue before
        # final_id is set
        seq = int(str(interest.getName()[-1]))
        if seq > final_id:
            semaphore.release()
            return

        logging.info('retry_or_fail(): {}'.format(interest.getName()))

        for _ in range(FETCHER_MAX_ATTEMPT_NUMBER):
            response = await fetch_data_packet(face, interest)
            success = False
            if isinstance(response, Data):
                final_id_component = response.metaInfo.getFinalBlockId()
                if final_id_component.isSegment():
                    final_id = final_id_component.toSegment()
                    logging.info('final_id is set to {}'.format(final_id))
                success = True
                break
            else:
                await asyncio.sleep(FETCHER_RETRY_INTERVAL / 1000.0)
        if success:
            n_success += 1
        else:
            n_fail += 1
        # Exit if all data fetched, or n_fail reaches a threshold
        if n_fail >= FETCHER_FAIL_EXIT_THRESHOLD or n_success + n_fail >= final_id - start_block_id + 1:
            done.set()

        semaphore.release()
        after_fetched(response)

    cur_id = (start_block_id if start_block_id else 0)
    final_id = (end_block_id if (end_block_id is not None) else 0x7fffffff)
    n_success = 0
    n_fail = 0
    event_loop = asyncio.get_event_loop()
    done = asyncio.Event()

    tasks = []
    while cur_id <= final_id:
        # Need to acquire semaphore before adding task to event loop, otherwise an unlimited
        # number of tasks would be added
        await semaphore.acquire()
        interest = Interest(Name(prefix).append(str(cur_id)))
        interest.setInterestLifetimeMilliseconds(1000)

        # Because asyncio is non-preemptive, need to explicitly release control here to give asyncio
        # a chance to process incoming data
        await asyncio.sleep(0)
        tasks.append(event_loop.create_task(retry_or_fail(interest)))
        cur_id += 1

        # Give up?
        if done.is_set():
            break

    await asyncio.gather(*tasks)
    await done.wait()

