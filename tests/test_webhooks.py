import requests

from hurricane.testing.drivers import HurricaneServerDriver
from hurricane.testing.testcases import HurricaneWebhookServerTest


class HurricaneWebhookStartServerTests(HurricaneWebhookServerTest):
    starting_message = "Started webhook receiver server"

    @HurricaneWebhookServerTest.cycle_server
    def test_webhook_on_success(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(
            params=["--command", "makemigrations", "--webhook-url", "http://localhost:8074/webhook"]
        )
        out, err = self.driver.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertIn(self.starting_message, out)
        self.assertIn("succeeded", out)

    @HurricaneWebhookServerTest.cycle_server
    def test_webhook_on_failure(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(
            params=["--command", "failingcommand", "--webhook-url", "http://localhost:8074/webhook"]
        )
        out, err = self.driver.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertIn(self.starting_message, out)
        self.assertIn("failed", out)

    @HurricaneWebhookServerTest.cycle_server
    def test_webhook_without_management_commands(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(params=["--webhook-url", "http://localhost:8074/webhook"])
        out, err = self.driver.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertIn(self.starting_message, out)
        self.assertIn("succeeded", out)

    @HurricaneWebhookServerTest.cycle_server
    def test_webhook_wrong_url(self):
        response = requests.post(
            "http://localhost:8074/web", timeout=5, data={"status": "succeeded", "type": "startup"}
        )
        self.assertEqual(response.status_code, 404)

    @HurricaneWebhookServerTest.cycle_server
    def test_liveness_webhook(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(params=["--webhook-url", "http://localhost:8074/webhook"])
        response = requests.get("http://localhost:8001/alive", timeout=5)
        out, err = self.driver.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.starting_message, out)
        self.assertIn("succeeded", out)

    @HurricaneWebhookServerTest.cycle_server
    def test_readiness_webhook(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(params=["--webhook-url", "http://localhost:8074/webhook"])
        response = requests.get("http://localhost:8001/ready", timeout=5)
        out, err = self.driver.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.starting_message, out)
        self.assertIn("succeeded", out)

    @HurricaneWebhookServerTest.cycle_server
    def test_readiness_webhook_request_queue_length(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(params=["--webhook-url", "http://localhost:8074/webhook", "--req-queue-len", "0"])
        response = requests.get("http://localhost:8001/ready", timeout=5)
        out, err = self.driver.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertEqual(response.status_code, 400)
        self.assertIn(self.starting_message, out)
        self.assertIn("failed", out)

    @HurricaneWebhookServerTest.cycle_server
    def test_get_webhook_from_registry(self):
        from hurricane.webhooks.base import Webhook
        from hurricane.webhooks.webhook_types import StartupWebhook

        Webhook(code="new_webhook")
        StartupWebhook.get_from_registry()
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
