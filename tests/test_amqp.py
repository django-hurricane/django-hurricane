from time import sleep

from hurricane.testing import HurricanAMQPTest


class HurricanStartAMQPTests(HurricanAMQPTest):
    def _wait_for_queue(self, queue_name="test"):
        # wait 10 seconds to bind to queue
        for i in range(0, 20):
            out, err = self.driver.get_output(read_all=True)
            if f"hurricane.amqp.general Binding to {queue_name}" in out:
                break
            sleep(0.5)
        else:
            self.fail("AMQP consumer did not bind to test queue")

    @HurricanAMQPTest.cylce_consumer(
        args=["tests.testapp.consumer.MyTestHandler", "--queue", "test", "--exchange", "test"]
    )
    def test_default_startup(self):
        out, err = self.driver.get_output(read_all=True)
        host, port = self.driver.get_amqp_host_port()
        self.assertIn("Starting a Tornado-powered Django AMQP consumer", out)
        self.assertIn(f"Connecting to {host}:{port}/", out)
        self._wait_for_queue()
        res = self.probe_client.get("/alive")
        self.assertEqual(res.status, 200)

    @HurricanAMQPTest.cylce_consumer(
        args=[
            "tests.testapp.consumer.MyTestHandler",
            "--queue",
            "test",
            "--exchange",
            "test",
            "--probe-port",
            "8080",
            "--probe",
            "probe",
        ]
    )
    def test_probe_startup(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("Starting a Tornado-powered Django AMQP consumer", out)
        self.assertIn("hurricane.amqp.general Probe application running on port 8080 with route /probe", out)
        res = self.probe_client.get("/probe")
        self.assertEqual(res.status, 200)

    @HurricanAMQPTest.cylce_consumer(
        args=["tests.testapp.consumer.MyTestHandler", "--queue", "test", "--exchange", "test", "--no-probe"]
    )
    def test_no_probe_startup(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("Starting a Tornado-powered Django AMQP consumer", out)
        self.assertIn("No probe application running", out)

    @HurricanAMQPTest.cylce_consumer(
        args=["tests.testapp.consumer.MyTestHandler", "--queue", "test", "--exchange", "test"]
    )
    def test_receive_message(self):
        testmessage = "This is a simple test message"
        publisher = self.driver.get_test_publisher()
        publisher.publish("test", "test", testmessage)
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(testmessage, out)

    @HurricanAMQPTest.cylce_consumer(
        args=["tests.testapp.consumer.MyTestHandler", "--queue", "test", "--exchange", "test"]
    )
    def test_connection_lost(self):
        # first connect successfully
        self._wait_for_queue()
        out, err = self.driver.get_output(read_all=True)
        self.assertNotIn("AMQP consumer running in auto-reconnect mode", out)
        # stop the broker
        self.driver.stop_amqp()
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("WARNING  hurricane.amqp.general Channel 1 was closed: Transport indicated EOF", out)
        # this must terminate immediately
        self.driver.proc.wait(5)
        self.assertIsNotNone(self.driver.proc.returncode)

    @HurricanAMQPTest.cylce_consumer(
        args=["tests.testapp.consumer.MyTestHandler", "--queue", "test", "--exchange", "test", "--reconnect"]
    )
    def test_reconnect_on_lost(self):
        # first connect successfully
        self._wait_for_queue()
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("AMQP consumer running in auto-reconnect mode", out)
        # stop the broker
        self.driver.halt_amqp()
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("WARNING  hurricane.amqp.general Channel 1 was closed: Transport indicated EOF", out)
        self.assertIn("WARNING  hurricane.amqp.general Reconnecting after 1 ", out)
        self.driver.start_amqp()
        self._wait_for_queue()

    @HurricanAMQPTest.cylce_consumer(
        args=["tests.testapp.consumer.MyTestHandler", "--queue", "test", "--exchange", "test"]
    )
    def test_disconnect(self):
        self._wait_for_queue()
        self.driver.stop_consumer()

    @HurricanAMQPTest.cylce_consumer(
        args=["tests.testapp.consumer.BindTestHandler", "--queue", "topic.read.consumer1", "--exchange", "test"]
    )
    def test_topic_publish_receive(self):
        self._wait_for_queue("topic.read")
        testmessage_read = "This is a simple test message"
        testmessage_not_read = "This is message must not read at the consumer"
        publisher = self.driver.get_test_publisher()
        publisher.publish("test", "topic.read", testmessage_read)
        publisher.publish("test", "topic.no", testmessage_read)
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(testmessage_read, out)
        self.assertNotIn(testmessage_not_read, out)
