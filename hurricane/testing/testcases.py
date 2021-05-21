import tornado.web
from django.test import SimpleTestCase

from hurricane.kubernetes import K8sServerMetricsHandler
from hurricane.testing.actors import HTTPClient, WebhookTestHandler
from hurricane.testing.drivers import (
    HurricaneAMQPDriver,
    HurricaneK8sServerDriver,
    HurricaneServerDriver,
    HurricaneWebhookServerDriver,
)


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

    def _retrieve_env(self, kwargs):
        return kwargs["env"] if "env" in kwargs else {}

    @staticmethod
    def cycle_server(*args, **kwargs):
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
                env = self._retrieve_env(kwargs)
                self.driver.start_server(_args, coverage, env)
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


class HurricaneWebhookServerTest(HurricanServerTest):
    driver = HurricaneWebhookServerDriver

    @property
    def probe(self):
        return WebhookTestHandler()


class HurricaneK8sServerTest(HurricanServerTest):
    driver = HurricaneK8sServerDriver

    @property
    def probe(self):
        return K8sServerMetricsHandler()


class HurricaneAMQPTest(HurricanBaseTest):
    driver = HurricaneAMQPDriver

    @classmethod
    def tearDownClass(cls):
        cls.driver.stop_consumer()
        cls.driver.stop_amqp()
        super().tearDownClass()

    def _retrieve_env(self, kwargs):
        return kwargs["env"] if "env" in kwargs else {}

    @staticmethod
    def cycle_consumer(*args, **kwargs):
        def _cycle_consumer(function):
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
                env = self._retrieve_env(kwargs)
                self.driver.start_amqp()
                if "--no_host_port" not in _args:
                    host, port = self.driver.get_amqp_host_port()
                    _args += ["--amqp-port", str(port), "--amqp-host", host]
                else:
                    _args = _args[:-1]
                self.driver.start_consumer(_args, coverage, env)
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
            return _cycle_consumer(args[0])
        else:
            return _cycle_consumer
