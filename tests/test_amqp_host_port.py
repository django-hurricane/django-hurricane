from time import sleep

from hurricane.testing import HurricaneAMQPPortHostTest


class HurricaneStartAMQPPortHostTests(HurricaneAMQPPortHostTest):

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

    @HurricaneAMQPPortHostTest.cycle_consumer(
        args=["tests.testapp.consumer.MyTestHandler", "--queue", "test", "--exchange", "test"]
    )
    def test_empty_host(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_amqp_message, out)
        self.assertIn(
            "CommandError: The amqp host must not be empty: set it either as environment AMQP_HOST, in the "
            "django settings as AMQP_HOST or as optional argument --amqp-host",
            out,
        )

    @HurricaneAMQPPortHostTest.cycle_consumer(
        args=[
            "tests.testapp.consumer.MyTestHandler",
            "--queue",
            "test",
            "--exchange",
            "test",
            "--amqp-host",
            "127.0.0.1",
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
