#!/usr/bin/env python3
"""
    Example subscriber for `util/pubsub.py`.

    @Author jonnykong@cs.ucla.edu
    @Date   2020-05-10
"""

import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import Name, NonStrictName
from ndn_python_repo.utils import PubSub


async def run_subscriber(app: NDNApp, subscriber_prefix: NonStrictName):
    pb = PubSub(app, subscriber_prefix)
    await pb.wait_for_ready()

    topic = Name.from_str('/topic_foo')
    pb.subscribe(topic, foo_cb)


def foo_cb(msg: bytes):
    print(f'topic /topic_foo received msg: {msg.decode()}')


def main():
    logging.basicConfig(format='[%(asctime)s]%(levelname)s:%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    subscriber_prefix = Name.from_str('/test_subscriber')
    app = NDNApp()

    try:
        app.run_forever(
            after_start=run_subscriber(app, subscriber_prefix))
    except FileNotFoundError:
        logging.warning('Error: could not connect to NFD')


if __name__ == '__main__':
    main()