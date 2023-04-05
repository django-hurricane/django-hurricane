from time import sleep

from django.test import SimpleTestCase

from hurricane.testing.testcases import HurricaneAMQPTest
from tests.test_utils import BasicProperties, Channel, Connection, Deliver


class HurricaneStartAMQPPortHostTests(HurricaneAMQPTest):
    starting_amqp_message = "Starting a Tornado-powered Django AMQP consumer"

    def _wait_for_queue(self, queue_name="test"):
        # wait 10 seconds to bind to queue
        for _ in range(20):
            out, err = self.driver.get_output(read_all=True)
            if f"hurricane.amqp.general Binding to {queue_name}" in out:
                break
            sleep(0.5)
        else:
            self.fail("AMQP consumer did not bind to test queue")

    @HurricaneAMQPTest.cycle_consumer(
        args=["tests.testapp.consumer.MyTestHandler", "--queue", "test", "--exchange", "test", "--no_host_port"]
    )
    def test_empty_host(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_amqp_message, out)
        self.assertIn(
            "CommandError: The amqp host must not be empty: set it either as environment AMQP_HOST, in the "
            "django settings as AMQP_HOST or as optional argument --amqp-host",
            out,
        )

    @HurricaneAMQPTest.cycle_consumer(
        args=[
            "tests.testapp.consumer.MyTestHandler",
            "--queue",
            "test",
            "--exchange",
            "test",
            "--amqp-host",
            "127.0.0.1",
            "--no_host_port",
        ]
    )
    def test_empty_port(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_amqp_message, out)
        self.assertIn(
            "CommandError: The amqp port must not be empty: set it either as environment AMQP_PORT, in the "
            "django settings as AMQP_PORT or as optional argument --amqp-port",
            out,
        )

    @HurricaneAMQPTest.cycle_consumer(
        args=[
            "tests.testapp.consumer.MyTestHandler",
            "--queue",
            "test",
            "--exchange",
            "test",
            "--amqp-host",
            "127.0.0.1",
            "--amqp-port",
            "8082",
            "--amqp-vhost",
            "test",
            "--no_host_port",
        ]
    )
    def test_vhost(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_amqp_message, out)

    @HurricaneAMQPTest.cycle_consumer(
        env={"DJANGO_SETTINGS_MODULE": "tests.testapp.settings_amqp"},
        args=[
            "tests.testapp.consumer.MyTestHandler",
            "--queue",
            "test",
            "--exchange",
            "test",
            "--no_host_port",
        ],
    )
    def test_amqp_settings(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_amqp_message, out)

    @HurricaneAMQPTest.cycle_consumer(
        env={"DJANGO_SETTINGS_MODULE": "tests.testapp.settings_amqp_environs"},
        args=[
            "tests.testapp.consumer.MyTestHandler",
            "--queue",
            "test",
            "--exchange",
            "test",
            "--no_host_port",
        ],
    )
    def test_amqp_settings_environs(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_amqp_message, out)

    @HurricaneAMQPTest.cycle_consumer(
        args=[
            "tests.testapp.consumer.IncorrectHandler",
            "--amqp-host",
            "127.0.0.1",
            "--amqp-port",
            "8082",
            "--amqp-vhost",
            "test",
        ],
    )
    def test_amqp_incorrect_handler(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_amqp_message, out)
        self.assertIn(
            "The type <class 'tests.testapp.consumer.IncorrectHandler'> is not subclass of _AMQPConsumer", out
        )
        self.assertIn("CommandError: Cannot start the consumer due to an implementation error", out)

    from hurricane.amqp.basehandler import _AMQPConsumer
    from hurricane.amqp.worker import AMQPClient

    amqp_consumer = _AMQPConsumer(queue_name="test", exchange_name="test", host="localhost", port=8075)
    amqp_client = AMQPClient(type(amqp_consumer), "test", "test", "test", 8083, "test")
    amqp_consumer._channel = Channel()

    def test_on_consumer_cancel(self):
        # pika.frame.Method(2, pika.amqp_object.Method())
        self.amqp_consumer._channel = Channel()
        self.amqp_consumer.on_consumer_cancelled("Test")

    def test_on_message(self):
        self.amqp_consumer._channel = Channel()
        with self.assertRaises(NotImplementedError):
            self.amqp_consumer.on_message(None, Deliver(), BasicProperties(), "")

    def test_stop_consuming(self):
        self.amqp_consumer.stop_consuming()

    def test_on_cancelok(self):
        self.amqp_consumer.on_cancelok(None, "Test")

    def test_on_connection_closed(self):
        self.amqp_consumer._closing = True
        self.amqp_consumer._connection = Connection()
        self.amqp_consumer.on_connection_closed(None, Exception("Test"))

    def test_stop(self):
        self.amqp_consumer._closing = False
        self.amqp_consumer._consuming = True
        self.amqp_consumer._connection = Connection()
        self.amqp_consumer.stop()

    def test_run_keyboard_interrupt(self):
        self.amqp_client._consumer._connection = Connection()
        import mock

        self.amqp_client._consumer.run = mock.Mock(side_effect=KeyboardInterrupt)
        self.amqp_client.run(reconnect=True)


class CycleServerException(SimpleTestCase):
    def test_cycle_server_function_exception_amqp(self):
        from tests.test_utils import simple_error_function

        with self.assertRaises(Exception):
            from hurricane.testing.testcases import HurricaneAMQPTest

            hurricane_server = HurricaneAMQPTest
            hurricane_server.cycle_consumer(simple_error_function())
