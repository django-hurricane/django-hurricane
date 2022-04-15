import os
import time
from typing import Type

import tornado.ioloop
from django.conf import settings

from hurricane.amqp import logger
from hurricane.amqp.basehandler import _AMQPConsumer


class AMQPClient(object):

    """
    This is the AMQP Client that will reconnect, if the nested handler instance indicates that a reconnect is necessary.
    """

    def __init__(
        self,
        consumer_klass: Type[_AMQPConsumer],
        queue_name: str,
        exchange_name: str,
        amqp_host: str,
        amqp_port: int,
        amqp_vhost: str,
    ):
        self._reconnect_delay = 0

        # load user
        if hasattr(settings, "AMQP_USER"):
            user = settings.AMQP_USER
        elif os.getenv("AMQP_USER"):
            user = os.getenv("AMQP_USER")
        else:
            user = None
        # load password
        if hasattr(settings, "AMQP_PASSWORD"):
            password = settings.AMQP_PASSWORD
        elif os.getenv("AMQP_PASSWORD"):
            password = os.getenv("AMQP_PASSWORD")
        else:
            password = None

        self._consumer_args = (queue_name, exchange_name, amqp_host, amqp_port, amqp_vhost, user, password)
        self._consumer_klass = consumer_klass
        self._consumer = self._consumer_klass(*self._consumer_args)

    def run(self, reconnect: bool = False) -> None:

        """
        If reconnect is True, AMQP consumer is running in auto-connect mode.
        In this case consumer will be executed. If any exception occurs, consumer will be disconnected and after some
        delay will be reconnected. Then consumer will be restarted. KeyboardInterrupt exception is handled
        differently and stops consumer. In this case IOLoop will be terminated.

        If reconnect is false, consumer will be started, but no exceptions and interruptions will be tolerated.
        """

        if reconnect:
            logger.info("AMQP consumer running in auto-reconnect mode")
            while True:
                try:
                    self._consumer.run()
                except KeyboardInterrupt:
                    self._consumer.stop()
                    break
                self._maybe_reconnect()
        else:
            self._consumer.run()
        logger.info("Terminating Hurricane AMQP client")
        loop = tornado.ioloop.IOLoop.current()
        loop.stop()

    def _maybe_reconnect(self) -> None:
        if self._consumer.should_reconnect:
            self._consumer.stop()
            reconnect_delay = self._get_reconnect_delay()
            logger.warning("Reconnecting after %d seconds", reconnect_delay)
            time.sleep(reconnect_delay)
            self._consumer = self._consumer_klass(*self._consumer_args)

    def _get_reconnect_delay(self):
        if self._consumer.was_consuming:
            self._reconnect_delay = 0
        else:
            self._reconnect_delay += 1
        self._reconnect_delay = min(self._reconnect_delay, 30)
        return self._reconnect_delay
