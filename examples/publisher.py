#!/usr/bin/env python3
"""
    Example publisher for `util/pubsub.py`.

    @Author jonnykong@cs.ucla.edu
    @Date   2020-05-10
"""

import asyncio as aio
import datetime
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName
from ndn_python_repo.utils import PubSub


async def run_publisher(app: NDNApp, publisher_prefix: NonStrictName):
    pb = PubSub(app, publisher_prefix)
    await pb.wait_for_ready()

    topic = Name.from_str('/topic_foo')
    msg = f'pubsub message generated at {str(datetime.datetime.now())}'.encode()
    pb.publish(topic, msg)

    # wait for msg to be fetched by subsciber
    await aio.sleep(10)
    app.shutdown()


def main():
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    publisher_prefix = Name.from_str('/test_publisher')
    app = NDNApp()

    try:
        app.run_forever(
            after_start=run_publisher(app, publisher_prefix))
    except FileNotFoundError:
        logging.warning('Error: could not connect to NFD')


if __name__ == '__main__':
    main()