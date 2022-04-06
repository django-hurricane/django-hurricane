from time import sleep

from hurricane.testing import HurricaneAMQPTest


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
