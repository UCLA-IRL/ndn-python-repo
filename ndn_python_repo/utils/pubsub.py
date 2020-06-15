# -----------------------------------------------------------------------------
# Pub-sub API.
#
# This pub-sub library provides best-effort, at-most-once delivery guarantee.
# If there are no subscribers reachable when a message is published, this
# message will not be re-transmitted.
# If there are multiple subscribers reachable, the nearest subscriber will be
# notified of the published message in an any-cast style.
#
# @Author jonnykong@cs.ucla.edu
# @Date   2020-05-08
# -----------------------------------------------------------------------------


import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import TlvModel, NameField, UintField
from ndn.encoding import Name, NonStrictName, Component, InterestParam
from ndn.name_tree import NameTrie
from ndn.types import InterestNack, InterestTimeout
from ndn.utils import gen_nonce


class PubSub(object):

    class NotifyAppParam(TlvModel):
        """
        Used to serialize application parameters for PubSub notify interest.
        """
        publisher_prefix = NameField()
        nonce = UintField(128)
        publisher_fwd_hint = NameField()

    def __init__(self, app: NDNApp, prefix: NonStrictName=None, forwarding_hint: NonStrictName=None):
        """
        Initialize a ``PubSub`` instance with identity ``prefix`` and can be reached at \
            ``forwarding_hint``.
        TODO: support msg larger than MTU

        :param app: NDNApp.
        :param prefix: NonStrictName. The identity of this ``PubSub`` instance. ``PubSub`` sends\
            Data packets under the hood to make pub-sub work, so it needs an identify under which\
            can publish data. Note that you cannot initialize two ``PubSub`` instances on the same\
            node, which will cause double registration error.
        :param forwarding_hint: NonStrictName. When working as publisher, if ``prefix`` is not\
            reachable, the subscriber can use ``forwarding_hint`` to reach the publisher.
        """
        self.app = app
        self.prefix = prefix
        self.forwarding_hint = forwarding_hint
        self.published_data = NameTrie()    # name -> packet
        self.topic_to_cb = NameTrie()

    def set_prefix(self, prefix: NonStrictName):
        """
        Set the identify of this ``PubSub`` instance after initialization.

        :param perfix: NonStrictName. The identity of this ``PubSub`` instance.
        """
        self.prefix = prefix

    async def wait_for_ready(self):
        """
        Need to be called to wait for pub-sub to be ready.
        """
        try:
            self.app.route(self.prefix + ['msg'])(self._on_msg_interest)
        except ValueError as esc:
            # duplicate registration
            pass

    def publish(self, topic: NonStrictName, msg: bytes):
        """
        Publish ``msg`` to ``topic``.

        :param topic: NonStrictName. The topic to publish ``msg`` to.
        :param msg: bytes. The message to publish. The pub-sub API does not make any assumptions on\
            the format of this message.
        """
        aio.ensure_future(self._publish_helper(topic, msg))

    def subscribe(self, topic: NonStrictName, cb: callable):
        """
        Subscribe to ``topic`` with ``cb``.

        :param topic: NonStrictName. The topic to subscribe to.
        :param cb: callable. A callback that will be called when a message under ``topic`` is\
            received. This function takes one ``bytes`` argument.
        """
        aio.ensure_future(self._subscribe_helper(topic, cb))

    def unsubscribe(self, topic: NonStrictName):
        """
        Unsubscribe from ``topic``.

        :param topic: NonStrictName. The topic to unsubscribe from.
        """
        logging.info(f'unsubscribing topic: {Name.to_str(topic)}')
        topic = Name.normalize(topic)
        del self.topic_to_cb[topic]

    async def _publish_helper(self, topic: NonStrictName, msg: bytes):
        """
        Async helper for `subscribe()``.
        """
        logging.info(f'publishing a message to topic: {Name.to_str(topic)}')
        # generate a nonce for each message
        nonce = gen_nonce()
        # wrap msg in a data packet named /<publisher_prefix>/msg/<topic>/nonce
        data_name = Name.normalize(self.prefix + ['msg'] + topic + [str(nonce)])
        self.published_data[data_name] = self.app.prepare_data(data_name, msg)

        # prepare notify interest
        int_name = topic + ['notify']
        app_param = PubSub.NotifyAppParam()
        app_param.publisher_prefix = self.prefix
        app_param.nonce = nonce
        if self.forwarding_hint:
            app_param.forwarding_hint = self.forwarding_hint

        aio.ensure_future(self._erase_state_after(data_name, 5))

        # express notify interest
        try:
            logging.debug(f'sending notify interest: {Name.to_str(int_name)}')
            data_name, meta_info, content = await self.app.express_interest(
                int_name, app_param.encode(), must_be_fresh=False, can_be_prefix=False)
        except InterestNack as e:
            logging.debug(f'Nacked with reason: {e.reason}')
            return
        except InterestTimeout:
            logging.debug(f'Timeout')
            return

        # if receiving notify response, the subscriber has finished fetching msg
        logging.debug(f'received notify response: {data_name}')
        await self._erase_state_after(data_name, 0)

    async def _subscribe_helper(self, topic: NonStrictName, cb: callable):
        """
        Async helper for ``subscribe()``.
        """
        logging.info(f'subscribing to topic: {Name.to_str(topic)}')
        topic = Name.normalize(topic)
        self.topic_to_cb[topic] = cb
        self.app.route(topic + ['notify'])(self._on_notify_interest)

    def _on_notify_interest(self, int_name, int_param, app_param):
        aio.ensure_future(self._process_notify_interest(int_name, int_param, app_param))

    async def _process_notify_interest(self, int_name, int_param, app_param):
        """
        Async helper for ``_on_notify_interest()``.
        """
        logging.debug(f'received notify interest: {Name.to_str(int_name)}')
        topic = int_name[:-2]   # remove digest and `notify`

        # parse notify interest
        app_param = PubSub.NotifyAppParam.parse(app_param)
        publisher_prefix = app_param.publisher_prefix
        nonce = app_param.nonce
        publisher_fwd_hint = app_param.publisher_fwd_hint
        int_param = InterestParam()
        if publisher_fwd_hint:
            int_param.forwarding_hint = publisher_fwd_hint

        # send msg interest, retransmit 3 times
        msg_int_name = publisher_prefix + ['msg'] + topic + [str(nonce)]
        n_retries = 3
        while n_retries > 0:
            try:
                logging.debug(f'sending msg interest: {Name.to_str(msg_int_name)}')
                data_name, meta_info, msg = await self.app.express_interest(
                    msg_int_name, int_param=int_param)
                break
            except InterestNack as e:
                logging.debug(f'Nacked with reason: {e.reason}')
                await aio.sleep(1)
            except InterestTimeout:
                logging.debug(f'Timeout')
        if msg == None:
            return

        # pass msg to application
        logging.info(f'received subscribed msg: {Name.to_str(msg_int_name)}')
        self.topic_to_cb[topic](bytes(msg))

        # acknowledge notify interest with an empty data packet
        logging.debug(f'acknowledging notify interest {Name.to_str(int_name)}')
        self.app.put_data(int_name, None)

    def _on_msg_interest(self, int_name, int_param, app_param):
        aio.ensure_future(self._process_msg_interest(int_name, int_param, app_param))

    async def _process_msg_interest(self, int_name, int_param, app_param):
        """
        Async helper for ``_on_msg_interest()``.
        The msg interest has the format of ``/<publisher_prefix>/msg/<topic>/<nonce>``.
        """
        logging.debug(f'received msg interest: {Name.to_str(int_name)}')
        if int_name in self.published_data:
            self.app.put_raw_packet(self.published_data[int_name])
            logging.debug(f'reply msg with name {Name.to_str(int_name)}')
        else:
            logging.debug(f'no matching msg with name {Name.to_str(int_name)}')

    async def _erase_state_after(self, name: NonStrictName, timeout: int):
        """
        Erase data with name ``name`` after ``timeout`` from application cache.
        """
        await aio.sleep(timeout)
        if name in self.published_data:
            del self.published_data[name]
            logging.debug(f'erased state for data {Name.to_str(name)}')
