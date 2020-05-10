"""
    Pub-sub API.

    This pub-sub library provides best-effort, at-most-once delivery guarantee. If there are
    multiple subscribers, the nearest subscriber will be notified in an any-cast style.

    @Author jonnykong@cs.ucla.edu
    @Date   2020-05-08
"""

import asyncio as aio
import logging
from ndn.app import NDNApp
from ndn.encoding import TlvModel, NameField, UintField
from ndn.encoding import Name, NonStrictName, Component
from ndn.types import InterestNack, InterestTimeout
from ndn.utils import gen_nonce


class NotifyAppParam(TlvModel):
    """
    Serialize application parameters for PubSub notify interest.
    """
    publisher_prefix = NameField()
    nonce = UintField(128)
    publisher_fwd_hint = NameField()


class PubSub(object):
    """
    Listens on `/prefix/notify` and `/prefix/msg`.
    """

    def __init__(self, app: NDNApp, prefix: NonStrictName, forwarding_hint: NonStrictName=None):
        """
        :param app: NDNApp.
        :param prefix: NonStrictName.
        """
        self.app = app
        self.prefix = prefix
        self.forwarding_hint = forwarding_hint
        self.nonce_to_msg= dict()
        self.topic_to_cb = dict()

    async def wait_for_ready(self):
        """
        Need to be called to wait for pub-sub to be ready.
        """
        await self.app.register(self.prefix + ['notify'], self._on_notify_interest)
        await self.app.register(self.prefix + ['msg'], self._on_msg_interest)

    def publish(self, topic: NonStrictName, msg: bytes):
        """
        Synchronous wrapper for ``_publish_helper()``.
        """
        aio.ensure_future(self._publish_helper(topic, msg))

    def subscribe(self, topic: NonStrictName, cb: callable):
        logging.info(f'subscribing to topic: {Name.to_str(topic)}')
        topic = Name.normalize(topic)
        self.topic_to_cb[topic] = cb

    def unsubscribe(self, topic: NonStrictName):
        logging.info(f'unsubscribing topic: {Name.to_str(topic)}')
        topic = Name.normalize(topic)
        del self.topic_to_cb[topic]

    async def _publish_helper(self, topic: NonStrictName, msg: bytes):
        nonce = gen_nonce()

        # wrap ``msg`` into a data packet
        # TODO: erase soft state
        data_name = self.prefix + [Component.from_number(nonce)]
        self.nonce_to_msg[nonce] = msg

        # prepare notify interest
        int_name = topic + ['notify']
        app_param = NotifyAppParam()
        app_param.publisher_prefix = self.prefix
        app_param.nonce = nonce
        if self.forwarding_hint:
            app_param.forwarding_hint = self.forwarding_hint

        # express notify interest
        try:
            data_name, meta_info, content = await self.app.express_interest(
                int_name, app_param.encode(), must_be_fresh=False, can_be_prefix=False)
        except InterestNack as e:
            logging.warning(f'Nacked with reason: {e.reason}') 
            return
        except InterestTimeout:
            logging.warning(f'Timeout')
            return
        logging.info(f'received notify response: {data_name}')
        logging.info('will erase soft state')

    async def _on_notify_interest(self, int_name, int_param, app_param):
        logging.info(f'received notify interest: {Name.to_str(int_name)}')
        topic = int_name[:-1]
        assert topic in self.topic_to_cb
        assert Component.to_str(int_name[-1]) == 'notify'

        # parse notify interest
        app_param = NotifyAppParam.parse(app_param)
        publisher_prefix = app_param.publisher_prefix
        nonce = app_param.nonce
        publisher_fwd_hint = app_param.publisher_fwd_hint

        # send msg interest
        int_name = publisher_fwd_hint + [nonce]
        data_name, meta_info, msg = await self.app.express_interest(int_name)

        # pass msg to application
        self.topic_to_cb[topic](msg)

    async def _on_msg_interest(self, int_name, int_param, app_param):
        logging.info(f'received msg interest: {Name.to_str(int_name)}')
        nonce = Component.to_number(int_name[-1])
        
        # return data if corresponding nonce still exists
        if nonce in self.nonce_to_msg:
            self.app.put_data(int_name, self.nonce_to_msg[nonce])
            logging.info(f'reply msg with name {Name.to_str(int_name)}')
        else:
            logging.info('no matching data found')