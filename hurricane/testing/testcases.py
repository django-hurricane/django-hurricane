from django.test import SimpleTestCase

from hurricane.testing.actors import HTTPClient
from hurricane.testing.drivers import HurricaneAMQPDriver, HurricaneServerDriver


class HurricanBaseTest(SimpleTestCase):
    driver = None

    @property
    def probe_client(self):
        host, port = self.driver.get_server_host_port(probe_port=True)
        return HTTPClient(host, port)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.driver = cls.driver()


class HurricanServerTest(HurricanBaseTest):
    driver = HurricaneServerDriver

    @property
    def app_client(self):
        host, port = self.driver.get_server_host_port()
        return HTTPClient(host, port)

    @classmethod
    def tearDownClass(cls):
        cls.driver.stop_server()
        super().tearDownClass()

    @staticmethod
    def cylce_server(*args, **kwargs):
        def _cycle_server(function):
            def wrapper(self):
                if "args" in kwargs:
                    _args = kwargs["args"]
                else:
                    _args = None
                # run this hurricane server with coverage
                # default is True
                if "coverage" in kwargs:
                    coverage = kwargs["coverage"]
                else:
                    coverage = True
                self.driver.start_server(_args, coverage)
                try:
                    function(self)
                except Exception as e:
                    self.driver.stop_server()
                    raise e
                else:
                    self.driver.stop_server()

            return wrapper

        if len(args) == 1 and callable(args[0]):
            return _cycle_server(args[0])
        else:
            return _cycle_server


class HurricanAMQPTest(HurricanBaseTest):
    driver = HurricaneAMQPDriver

    @classmethod
    def tearDownClass(cls):
        cls.driver.stop_consumer()
        cls.driver.stop_amqp()
        super().tearDownClass()

    @staticmethod
    def cylce_consumer(*args, **kwargs):
        def _cylce_consumer(function):
            def wrapper(self):
                if "args" in kwargs:
                    _args = kwargs["args"]
                else:
                    _args = None
                # run this hurricane consumer with coverage
                # default is True
                if "coverage" in kwargs:
                    coverage = kwargs["coverage"]
                else:
                    coverage = True
                self.driver.start_amqp()
                host, port = self.driver.get_amqp_host_port()
                _args += ["--amqp-port", str(port), "--amqp-host", host]
                self.driver.start_consumer(_args, coverage)
                try:
                    function(self)
                except Exception as e:
                    self.driver.stop_consumer()
                    self.driver.stop_amqp()
                    raise e
                else:
                    self.driver.stop_consumer()
                    self.driver.stop_amqp()

            return wrapper

        if len(args) == 1 and callable(args[0]):
            return _cylce_consumer(args[0])
        else:
            return _cylce_consumer