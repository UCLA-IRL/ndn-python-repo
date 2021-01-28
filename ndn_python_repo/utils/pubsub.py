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
from ndn.encoding import TlvModel, ModelField, NameField, BytesField
from ndn.encoding import Name, NonStrictName, Component, InterestParam
from ndn.name_tree import NameTrie
from ndn.types import InterestNack, InterestTimeout
import os


class PubSub(object):
    def __init__(self, app: NDNApp, prefix: NonStrictName=None, forwarding_hint: NonStrictName=None):
        """
        Initialize a ``PubSub`` instance with identity ``prefix`` and can be reached at \
            ``forwarding_hint``.
        TODO: support msg larger than MTU

        :param app: NDNApp.
        :param prefix: NonStrictName. The identity of this ``PubSub`` instance. The publisher needs\
            a prefix under which can publish data. Note that you cannot initialize two ``PubSub``\
            instances with the same ``prefix`` on the same node, since it will cause double\
            registration error.
        :param forwarding_hint: NonStrictName. When working as publisher, if ``prefix`` is not\
            reachable, the subscriber can use ``forwarding_hint`` to reach the publisher.
        """
        self.app = app
        self.publisher_prefix = prefix
        self.forwarding_hint = forwarding_hint
        self.base_prefix = None
        self.published_data = NameTrie()    # name -> packet
        self.topic_to_cb = NameTrie()
        self.nonce_processed = set()        # used by subscriber to de-duplicate notify interests

    def set_publisher_prefix(self, prefix: NonStrictName):
        """
        Set the identify of the publisher after initialization.
        Need to be called before ``_wait_for_ready()``.

        :param prefix: NonStrictName. The identity of this ``PubSub`` instance.
        """
        self.publisher_prefix = prefix
    
    def set_base_prefix(self, prefix: NonStrictName):
        """
        Avoid registering too many prefixes, by registering ``prefix`` with NFD. All other prefixes\
        under ``prefix`` will be registered with interest filters, and will not have to be\
        registered with NFD.
        Need to be called before ``_wait_for_ready()``.

        :param prefix: NonStrictName. The base prefix to register.
        """
        self.base_prefix = prefix

    async def wait_for_ready(self):
        """
        Need to be called to wait for pub-sub to be ready.
        """
        # Wait until app connected, otherwise app.register() throws an NetworkError
        while not self.app.face.running:
            await aio.sleep(0.1)

        if self.base_prefix != None:
            try:
                await self.app.register(self.base_prefix, func=None)
            except ValueError as esc:
                pass
        
        try:
            if self.base_prefix != None and Name.is_prefix(self.base_prefix, self.publisher_prefix + ['msg']):
                self.app.set_interest_filter(self.publisher_prefix + ['msg'], self._on_msg_interest)
            else:
                    await self.app.register(self.publisher_prefix + ['msg'], self._on_msg_interest)
        except ValueError as esc:
            # duplicate registration
            pass


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

    async def publish(self, topic: NonStrictName, msg: bytes):
        """
        Publish ``msg`` to ``topic``. Make several attempts until the subscriber returns a\
            response.

        :param topic: NonStrictName. The topic to publish ``msg`` to.
        :param msg: bytes. The message to publish. The pub-sub API does not make any assumptions on\
            the format of this message.
        :return: Return true if received response from a subscriber.
        """
        logging.info(f'publishing a message to topic: {Name.to_str(topic)}')
        # generate a nonce for each message. Nonce is a random sequence of bytes
        nonce = os.urandom(4)
        # wrap msg in a data packet named /<publisher_prefix>/msg/<topic>/nonce
        data_name = Name.normalize(self.publisher_prefix + ['msg'] + topic + [Component.from_bytes(nonce)])
        self.published_data[data_name] = self.app.prepare_data(data_name, msg)

        # prepare notify interest
        int_name = topic + ['notify']
        app_param = NotifyAppParam()
        app_param.publisher_prefix = self.publisher_prefix
        app_param.notify_nonce = nonce
        if self.forwarding_hint:
            app_param.publisher_fwd_hint = ForwardingHint()
            app_param.publisher_fwd_hint.name = self.forwarding_hint

        aio.ensure_future(self._erase_publisher_state_after(data_name, 5))

        # express notify interest
        n_retries = 3
        is_success = False
        while n_retries > 0:
            try:
                logging.debug(f'sending notify interest: {Name.to_str(int_name)}')
                _, _, _ = await self.app.express_interest(
                    int_name, app_param.encode(), must_be_fresh=False, can_be_prefix=False)
                is_success = True
                break
            except InterestNack as e:
                logging.debug(f'Nacked with reason: {e.reason}')
                await aio.sleep(1)
                n_retries -= 1
            except InterestTimeout:
                logging.debug(f'Timeout')
                n_retries -= 1

        # if receiving notify response, the subscriber has finished fetching msg
        if is_success:
            logging.debug(f'received notify response for: {data_name}')
        else:
            logging.debug(f'did not receive notify response for: {data_name}')
        await self._erase_publisher_state_after(data_name, 0)
        return is_success

    async def _subscribe_helper(self, topic: NonStrictName, cb: callable):
        """
        Async helper for ``subscribe()``.
        """
        topic = Name.normalize(topic)
        self.topic_to_cb[topic] = cb
        to_register = topic + ['notify']
        if self.base_prefix != None and Name.is_prefix(self.base_prefix, to_register):
            self.app.set_interest_filter(to_register, self._on_notify_interest)
            logging.info(f'Subscribing to topic (with interest filter): {Name.to_str(topic)}')
        else:
            await self.app.register(to_register, self._on_notify_interest)
            logging.info(f'Subscribing to topic: {Name.to_str(topic)}')

    def _on_notify_interest(self, int_name, int_param, app_param):
        aio.ensure_future(self._process_notify_interest(int_name, int_param, app_param))

    async def _process_notify_interest(self, int_name, int_param, app_param):
        """
        Async helper for ``_on_notify_interest()``.
        """
        logging.debug(f'received notify interest: {Name.to_str(int_name)}')
        topic = int_name[:-2]   # remove digest and `notify`

        # parse notify interest
        app_param = NotifyAppParam.parse(app_param)
        publisher_prefix = app_param.publisher_prefix
        notify_nonce = app_param.notify_nonce
        publisher_fwd_hint = app_param.publisher_fwd_hint
        int_param = InterestParam()
        if publisher_fwd_hint:
            # support only 1 forwarding hint now
            int_param.forwarding_hint = [(0x0, publisher_fwd_hint.name)]

        # send msg interest, retransmit 3 times
        msg_int_name = publisher_prefix + ['msg'] + topic + [Component.from_bytes(notify_nonce)]
        n_retries = 3

        # de-duplicate notify interests of the same nonce
        if notify_nonce in self.nonce_processed:
            logging.info(f'Received duplicate notify interest for nonce {notify_nonce}')
            return
        self.nonce_processed.add(notify_nonce)
        aio.ensure_future(self._erase_subsciber_state_after(notify_nonce, 60))

        msg = None
        while n_retries > 0:
            try:
                logging.debug(f'sending msg interest: {Name.to_str(msg_int_name)}')
                data_name, meta_info, msg = await self.app.express_interest(
                    msg_int_name, int_param=int_param)
                break
            except InterestNack as e:
                logging.debug(f'Nacked with reason: {e.reason}')
                await aio.sleep(1)
                n_retries -= 1
            except InterestTimeout:
                logging.debug(f'Timeout')
                n_retries -= 1
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

    async def _erase_publisher_state_after(self, name: NonStrictName, timeout: int):
        """
        Erase data with name ``name`` after ``timeout`` from application cache.
        """
        await aio.sleep(timeout)
        if name in self.published_data:
            del self.published_data[name]
            logging.debug(f'erased state for data {Name.to_str(name)}')

    async def _erase_subsciber_state_after(self, notify_nonce: bytes, timeout: int):
        """
        Erase state associated with nonce ``nonce`` after ``timeout``.
        """
        await aio.sleep(timeout)
        if notify_nonce in self.nonce_processed:
            self.nonce_processed.remove(notify_nonce)


class ForwardingHint(TlvModel):
    name = NameField()

class NotifyAppParam(TlvModel):
    """
    Used to serialize application parameters for PubSub notify interest.
    """
    publisher_prefix = NameField()
    notify_nonce = BytesField(128)
    publisher_fwd_hint = ModelField(211, ForwardingHint)
