import asyncio
import functools
from typing import List

import pika
from pika.adapters.tornado_connection import TornadoConnection

from hurricane.amqp import logger


class _AMQPConsumer:

    """
    This is Hurricane's base AMQP consumer that will handle unexpected interactions
    with the message broker such as channel and connection closures.
    If the message broker closes the connection, this class will stop and indicate
    that reconnection is necessary.
    """

    EXCHANGE_TYPE = None

    def __init__(
        self,
        queue_name: str,
        exchange_name: str,
        host: str,
        port: int,
        vhost: str = None,
        username: str = None,
        password: str = None,
    ):
        """
        Create a new instance of the consumer class, passing in the AMQP
        URL used to connect to broker.
        """
        self.should_reconnect = False
        self.was_consuming = False

        self._queue_name = queue_name
        self._exchange_name = exchange_name
        self._host = host
        self._port = port
        self._vhost = vhost or "/"
        self._username = username
        self._password = password

        self._connection = None
        self._channel = None
        self._closing = False
        self._consumer_tag = None
        self._consuming = False
        self._prefetch_count = 1

    def connect(self) -> TornadoConnection:

        """
        This method connects to the broker, returning the connection handle.
        """

        logger.info(f"Connecting to {self._host}:{self._port}{self._vhost}")
        # set amqp credentials
        if self._username:
            credentials = pika.PlainCredentials(self._username, self._password)
            # set amqp connection parameters
            parameters = pika.ConnectionParameters(
                host=self._host,
                port=self._port,
                virtual_host=self._vhost,
                credentials=credentials,
            )
        else:
            parameters = pika.ConnectionParameters(
                host=self._host,
                port=self._port,
                virtual_host=self._vhost,
            )

        # connect
        connection = TornadoConnection(
            parameters=parameters,
            on_open_callback=self.on_connection_open,
            on_open_error_callback=self.on_connection_open_error,
            on_close_callback=self.on_connection_closed,
        )
        return connection

    def close_connection(self):
        self._consuming = False
        if self._connection.is_closing or self._connection.is_closed:
            logger.info("Connection is closing or already closed")
        else:
            logger.info("Closing connection")
            self._connection.close()

    def on_connection_open(self, _unused_connection: pika.SelectConnection):

        """
        This method is called by pika once the connection to the broker has
        been established.
        """

        logger.info("Connection opened")
        self.open_channel()

    def on_connection_open_error(self, _unused_connection: pika.SelectConnection, err: Exception):

        """
        This method is called by pika if the connection to the broker
        can't be established.
        :param pika.SelectConnection _unused_connection: The connection
        :param Exception err: The error
        """

        logger.error(f"Connection open failed: {err}")
        self.reconnect()

    def on_connection_closed(self, _unused_connection: pika.SelectConnection, reason: Exception):

        """
        This method is invoked by pika when the connection to the broker is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        the broker if it disconnects.
        """

        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            logger.warning("Connection closed, reconnect necessary: %s", reason)
            self.reconnect()

    def reconnect(self):

        """
        Will be invoked if the connection can't be opened or is
        closed. Indicates that a reconnect is necessary then stops the
        ioloop.
        """

        self.should_reconnect = True
        self.stop()

    def open_channel(self):

        """
        Open a new channel with the broker by issuing the Channel.Open RPC
        command. When the broker responds that the channel is open, the
        on_channel_open callback will be invoked by pika.
        """

        logger.info("Creating a new channel")
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel: pika.channel.Channel):

        """
        This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.
        Since the channel is now open, we'll declare the exchange to use.
        """

        logger.info("Channel opened")
        self._channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange(self._exchange_name)

    def add_on_channel_close_callback(self):

        """
        This method tells pika to call the on_channel_closed method if
        the broker unexpectedly closes the channel.
        """

        logger.info("Adding channel close callback")
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel: pika.channel.Channel, reason: Exception):

        """
        Invoked by pika when the broker unexpectedly closes the channel.
        Channels are usually closed if you attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. In this case, we'll close the connection
        to shutdown the object.
        """

        logger.warning("Channel %i was closed: %s", channel, reason)
        self.close_connection()

    def setup_exchange(self, exchange_name: str) -> None:

        """
        Setup the exchange on the broker by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.
        """

        logger.info(f"Declaring exchange: {exchange_name}")
        # Note: using functools.partial is not required, it is demonstrating
        # how arbitrary data can be passed to the callback when it is called
        cb = functools.partial(self.on_exchange_declareok, userdata=exchange_name)
        self._channel.exchange_declare(exchange=exchange_name, exchange_type=self.EXCHANGE_TYPE, callback=cb)

    def on_exchange_declareok(self, _unused_frame: pika.frame.Method, userdata: str) -> None:

        """
        Invoked by pika when the broker has finished the Exchange.Declare RPC
        command.
        """

        logger.info("Exchange declared: %s", userdata)
        self.setup_queue(self._queue_name)

    def setup_queue(self, queue_name: str) -> None:

        """
        Setup the queue on the broker by invoking the Queue.Declare RPC
        command. When it is complete, the on_queue_declareok method will
        be invoked by pika.
        :param str|unicode queue_name: The name of the queue to declare.
        """

        logger.info(f"Declaring queue {queue_name}")
        cb = functools.partial(self.on_queue_declareok, userdata=queue_name)
        self._channel.queue_declare(queue=queue_name, callback=cb)

    def get_routing_keys(self, queue_name: str) -> List[str]:

        """
        Generate a list of binding keys for this queue. This method will
        be called from on_queue_declareok in order to bind the declared queue
        on to one or multiple routing keys.
        """

        return []

    def on_queue_declareok(self, _unused_frame: pika.frame.Method, userdata: str) -> None:

        """
        Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the Queue.Bind
        RPC command. When this command is complete, the on_bindok method will
        be invoked by pika.
        """

        queue_name = userdata
        logger.info(f"Binding to {queue_name}")
        routing_keys = self.get_routing_keys(queue_name)
        if len(routing_keys) == 0:
            # no routing key applicable
            cb = functools.partial(self.on_bindok, queue_name=queue_name)
            self._channel.queue_bind(queue_name, exchange=self._exchange_name, callback=cb)
        else:
            for routing_key in routing_keys:
                cb = functools.partial(self.on_bindok, queue_name=queue_name, routing_key=routing_key)
                self._channel.queue_bind(queue_name, routing_key=routing_key, exchange=self._exchange_name, callback=cb)

    def on_bindok(self, _unused_frame: pika.frame.Method, queue_name: str, routing_key: str = None):

        """
        Invoked by pika when the Queue.Bind method has completed. At this
        point we will set the prefetch count for the channel.
        """

        if routing_key:
            logger.info(f"Queue bound: {queue_name} with routing key {routing_key}")
        else:
            logger.info(f"Queue bound: {queue_name}")
        self.set_qos()

    def set_qos(self) -> None:

        """
        This method sets up the consumer prefetch to only be delivered
        one message at a time. The consumer must acknowledge this message
        before the broker will deliver another one. You should experiment
        with different prefetch values to achieve desired performance.
        """

        self._channel.basic_qos(prefetch_count=self._prefetch_count, callback=self.on_basic_qos_ok)

    def on_basic_qos_ok(self, _unused_frame) -> None:

        """
        Invoked by pika when the Basic.QoS method has completed. At this
        point we will start consuming messages by calling start_consuming
        which will invoke the needed RPC commands to start the process.
        :param pika.frame.Method _unused_frame: The Basic.QosOk response frame
        """

        logger.info(f"QOS set to: {self._prefetch_count}")
        self.start_consuming()

    def start_consuming(self) -> None:

        """
        This method sets up the consumer by first calling
        add_on_cancel_callback so that the object is notified if the broker
        cancels the consumer.
        """

        logger.info("Issuing consumer")
        self.add_on_cancel_callback()
        self._consumer_tag = self._channel.basic_consume(self._queue_name, self.on_message)
        self.was_consuming = True
        self._consuming = True

    def add_on_cancel_callback(self) -> None:

        """
        Add a callback that will be invoked if the broker cancels the consumer
        for some reason. If the broker does cancel the consumer,
        on_consumer_cancelled will be invoked by pika.
        """

        logger.info("Adding consumer cancellation callback")
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame: pika.frame.Method) -> None:

        """
        Invoked by pika when the broker sends a Basic.Cancel for a consumer
        receiving messages.
        """

        logger.info(f"Consumer was cancelled remotely, shutting down: {method_frame}")
        if self._channel:
            self._channel.close()

    def on_message(
        self,
        _unused_channel: pika.channel.Channel,
        basic_deliver: pika.spec.Basic.Deliver,
        properties: pika.spec.BasicProperties,
        body: str,
    ) -> None:

        """
        Invoked by pika when a message is delivered from the broker.
        """

        logger.error(
            "Received message # %s from %s",
            basic_deliver.delivery_tag,
            properties.app_id,
        )
        self.reject_message(basic_deliver.delivery_tag)
        raise NotImplementedError("The on_message method must be implemented by a handler class")

    def acknowledge_message(self, delivery_tag) -> None:

        """
        Acknowledge the message delivery from the broker by sending a
        Basic.Ack RPC method for the delivery tag.
        :param int delivery_tag: The delivery tag from the Basic.Deliver frame
        """

        logger.info("Acknowledging message %s", delivery_tag)
        self._channel.basic_ack(delivery_tag)

    def reject_message(self, delivery_tag, requeue: bool = False) -> None:

        """
        Reject the message delivery from the broker.
        """

        logger.info("Rejecting message %s", delivery_tag)
        self._channel.basic_nack(delivery_tag, requeue=requeue)

    def stop_consuming(self) -> None:

        """
        Tell the broker that you would like to stop consuming by sending the
        Basic.Cancel RPC command.
        """

        if self._channel:
            logger.info("Sending a Basic.Cancel command to the broker")
            cb = functools.partial(self.on_cancelok, userdata=self._consumer_tag)
            self._channel.basic_cancel(self._consumer_tag, cb)

    def on_cancelok(self, _unused_frame: pika.frame.Method, userdata: str) -> None:

        """
        This method is invoked by pika when the broker acknowledges the
        cancellation of a consumer. At this point we will close the channel.
        This will invoke the on_channel_closed method once the channel has been
        closed, which will in-turn close the connection.
        """

        self._consuming = False
        logger.info(f"The broker acknowledged the cancellation of the consumer: {userdata}")
        self.close_channel()

    def close_channel(self) -> None:

        """
        Call to close the channel cleanly by issuing the
        Channel.Close RPC command.
        """

        logger.info("Closing the channel")
        self._channel.close()

    def run(self) -> None:

        """
        Run the consumer by connecting to the broker and then
        starting the IOLoop to block and allow the SelectConnection to operate.
        """

        self._connection = self.connect()
        self._connection.ioloop.start()

    def stop(self) -> None:

        """
        Cleanly shutdown the connection by stopping the consumer.
        """

        if not self._closing:
            self._closing = True
            logger.info("Stopping")
            if self._consuming:
                self.stop_consuming()
                logger.info("Start called")
                self._connection.ioloop.stop()
            else:
                self._connection.ioloop.stop()
            logger.info("Stopped consuming")


class TopicHandler(_AMQPConsumer):

    """
    This handler implements Hurricane's base AMQP consumer that handles unexpected interactions
    with the message broker such as channel and connection closures. The ``EXCHANGE_TYPE`` is *topic*.
    """

    EXCHANGE_TYPE = "topic"
