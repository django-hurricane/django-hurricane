from hurricane.testing.drivers import HurricaneServerDriver
from hurricane.testing.testcases import HurricaneWebhookServerTest


class HurricaneWebhookStartServerTests(HurricaneWebhookServerTest):
    @HurricaneWebhookServerTest.cycle_server
    def test_webhook_on_success(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(
            params=["--command", "makemigrations", "--startup-webhook", "http://localhost:8074/webhook"]
        )
        out, err = self.driver.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertIn("Started webhook receiver server", out)
        self.assertIn("succeeded", out)

    @HurricaneWebhookServerTest.cycle_server
    def test_webhook_on_failure(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(
            params=["--command", "migrate", "--startup-webhook", "http://localhost:8074/webhook"]
        )
        out, err = self.driver.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertIn("Started webhook receiver server", out)
        self.assertIn("failed", out)

    @HurricaneWebhookServerTest.cycle_server
    def test_webhook_without_management_commands(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(params=["--startup-webhook", "http://localhost:8074/webhook"])
        out, err = self.driver.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertIn("Started webhook receiver server", out)
        self.assertIn("succeeded", out)

    @HurricaneWebhookServerTest.cycle_server
    def test_webhook_wrong_url(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(params=["--startup-webhook", "http://localhost:8074/web"])
        out, err = self.driver.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertIn("Started webhook receiver server", out)
        self.assertIn("WARNING", out)
        self.assertIn("404", out)
