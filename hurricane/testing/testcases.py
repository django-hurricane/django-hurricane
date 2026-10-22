from typing import Any

from django.test import SimpleTestCase

from hurricane.testing.actors import HTTPClient, WebhookTestHandler
from hurricane.testing.drivers import (
    HurricaneServerDriver,
    HurricaneWebhookServerDriver,
)


class HurricanBaseTest(SimpleTestCase):
    driver: Any = None

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
    driver = HurricaneWebhookServerDriver  # type: ignore

    @property
    def probe(self):
        return WebhookTestHandler()
