import asyncio
import threading
from typing import Union, Dict, List
from pyndn import Face, Interest, NetworkNack, Data, Name


async def fetch_data_packet(face: Face, interest: Interest) -> Union[Data, NetworkNack, None]:
    done = threading.Event()
    result = None

    def on_data(_interest, data: Data):
        nonlocal done, result
        result = data
        print("on_data")
        done.set()

    def on_timeout(_interest):
        nonlocal done
        print("on_timeout")
        done.set()

    def on_network_nack(_interest, network_nack: NetworkNack):
        nonlocal done, result
        result = network_nack
        print("on_nack")
        done.set()

    async def wait_for_event():
        ret = False
        while not ret:
            ret = done.wait(0.01)
            await asyncio.sleep(0.01)

    try:
        face.expressInterest(interest, on_data, on_timeout, on_network_nack)
        await wait_for_event()
        return result
    except (ConnectionRefusedError, BrokenPipeError) as error:
        return error

