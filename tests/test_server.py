import os
import re

import requests

from hurricane.server import signal_handler, static_watch
from hurricane.testing import HurricanServerTest
from hurricane.testing.drivers import BusyPortException, HurricaneServerDriver

current_dir = os.getcwd()
STATIC_PATH = os.makedirs(f"{current_dir}/static")

class HurricanStartServerTests(HurricanServerTest):

    probe_route = "/probe"
    alive_route = "/alive"
    startup_route = "/startup"
    ready_route = "/ready"
    starting_message = "Tornado-powered Django web server"
    starting_management_commands_message = "Starting execution of management commands"
    starting_http_message = "Starting HTTP Server on port 8000"

    @HurricanServerTest.cycle_server
    def test_default_startup(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn(
            "Starting probe application running on port 8001 with route liveness-probe: /alive, readiness-probe: /ready, startup-probe: /startup",
            out,
        )
        self.assertIn(self.starting_http_message, out)

    @HurricanServerTest.cycle_server(coverage=True)
    def test_default_startup_coverage_kwarg(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn(
            "Starting probe application running on port 8001 with route liveness-probe: /alive, readiness-probe: /ready, startup-probe: /startup",
            out,
        )
        self.assertIn(self.starting_http_message, out)

    @HurricanServerTest.cycle_server(args=["--port", "8085"])
    def test_port_startup(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn(
            "Starting probe application running on port 8086 with route liveness-probe: /alive, readiness-probe: /ready, startup-probe: /startup",
            out,
        )

    @HurricanServerTest.cycle_server(args=["--no-probe"])
    def test_no_probe(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("No probe application running", out)

    @HurricanServerTest.cycle_server(args=["--startup-probe", "probe", "--probe-port", "8090"])
    def test_probe_startup(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("Starting probe application running on port 8090 with route", out)
        res = self.probe_client.get(self.probe_route)
        self.assertEqual(res.status, 200)
        res = self.probe_client.post(self.probe_route, data=None)
        self.assertEqual(res.status, 200)
        res = self.probe_client.post(self.probe_route + "/", data=None)
        self.assertEqual(res.status, 200)
        res = self.probe_client.post(self.probe_route + "//", data=None)
        self.assertEqual(res.status, 404)

    @HurricanServerTest.cycle_server(args=["--startup-probe", "/probe/", "--probe-port", "8090"])
    def test_probe_startup_trail_slash(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("Starting probe application running on port 8090 with route", out)
        res = self.probe_client.get(self.probe_route)
        self.assertEqual(res.status, 200)
        res = self.probe_client.get(self.probe_route + "/")
        self.assertEqual(res.status, 200)
        res = self.probe_client.get(self.probe_route + "//")
        self.assertEqual(res.status, 404)

    @HurricanServerTest.cycle_server(args=["--startup-probe", "probe", "--probe-port", "8000", "--port", "8000"])
    def test_probe_integrated_startup(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("running integrated on port 8000", out)
        res = self.probe_client.get(self.probe_route)
        self.assertEqual(res.status, 200)

    @HurricanServerTest.cycle_server(args=["--no-metrics", "--probe-port", "8090"])
    def test_nometrics_startup(self):
        res = self.probe_client.get(self.alive_route)
        self.assertEqual(res.status, 200)
        self.assertIn("alive", res.text)

    @HurricanServerTest.cycle_server
    def test_request(self):
        res = self.app_client.get("/")
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(res.status, 200)
        self.assertIn("200 GET / ", out)
        self.assertIn("Hello world", res.text)

    @HurricanServerTest.cycle_server(args=["--static", "--media"])
    def test_serve_statics_and_media(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn(
            "Starting probe application running on port 8001 with route liveness-probe: /alive, readiness-probe: /ready, startup-probe: /startup",
            out,
        )
        self.assertIn(" Serving static files under /static/", out)
        self.assertIn("Serving media files under /media/", out)

    @HurricanServerTest.cycle_server
    def test_metrics_request(self):
        self.app_client.get("/")
        res = self.probe_client.get(self.alive_route)
        self.assertEqual(res.status, 200)
        self.assertIn("Average response time:", res.text)

    def _get_timing_from_string(self, string: str) -> str:
        m = re.compile(r"(?P<value>[0-9]*\.[0-9]{2})ms")
        match = m.search(string)
        if match:
            return match.group("value")

    @HurricanServerTest.cycle_server
    def test_metrics_average_response_time(self):
        self.app_client.get("/")
        self.app_client.get("/")
        self.app_client.get("/")
        out, err = self.driver.get_output(read_all=True)
        result = 0
        for line in out.split("\n"):
            timing = self._get_timing_from_string(line)
            if timing:
                result += float(timing)
        result /= 3
        res = self.probe_client.get(self.alive_route)

        timing = float(self._get_timing_from_string(res.text))
        self.assertEqual(res.status, 200)
        self.assertAlmostEqual(result, timing, 1)

    @HurricanServerTest.cycle_server
    def test_log_outputs(self):
        out, err = self.driver.get_output(read_all=True)
        res = self.app_client.get("/doesnotexist")
        self.assertEqual(res.status, 404)
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(" 404 GET /doesnotexist", out)
        res = self.app_client.get("/")
        self.assertEqual(res.status, 200)

    @HurricanServerTest.cycle_server
    def test_head_request(self):
        res = self.app_client.head("/")
        self.assertEqual(res.status, 200)
        self.assertEqual(res.text, "")

    @HurricanServerTest.cycle_server(args=["--autoreload"])
    def test_autoreload(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("Autoreload was performed", out)
        self.assertIn(self.starting_http_message, out)

    @HurricanServerTest.cycle_server(args=["--command", "makemigrations", "--probe-port", "8090"])
    def test_startup_with_single_management_command(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("Starting probe application running on port 8090", out)
        self.assertIn(self.starting_management_commands_message, out)
        self.assertIn(self.starting_http_message, out)

        res = self.probe_client.get(self.startup_route)
        self.assertEqual(res.status, 200)
        res = self.probe_client.post(self.startup_route, data=None)
        self.assertEqual(res.status, 200)
        res = self.probe_client.get(self.alive_route)
        self.assertEqual(res.status, 200)
        res = self.probe_client.get(self.ready_route)
        self.assertEqual(res.status, 200)
        res = self.app_client.get("/")
        self.assertEqual(res.status, 200)

    @HurricanServerTest.cycle_server(
        args=["--command", "makemigrations", "--command", "makemigrations", "--probe-port", "8090"]
    )
    def test_startup_with_multiple_management_commands(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("Starting probe application running on port 8090 with route", out)
        self.assertIn(self.starting_management_commands_message, out)
        self.assertIn("No changes detected", out)
        self.assertIn(self.starting_http_message, out)

        res = self.probe_client.get(self.startup_route)
        self.assertEqual(res.status, 200)
        res = self.probe_client.post(self.startup_route, data=None)
        self.assertEqual(res.status, 200)
        res = self.probe_client.get(self.alive_route)
        self.assertEqual(res.status, 200)
        res = self.probe_client.get(self.ready_route)
        self.assertEqual(res.status, 200)
        res = self.app_client.get("/")
        self.assertEqual(res.status, 200)

    @HurricanServerTest.cycle_server(args=["--command", "failingcommand", "--probe-port", "8090"])
    def test_startup_failing_management_command(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn(
            "Starting probe application running on port 8090 with route liveness-probe: /alive, readiness-probe: /ready, startup-probe: /startup",
            out,
        )
        self.assertIn(self.starting_management_commands_message, out)
        self.assertIn("ERROR", out)

    @HurricanServerTest.cycle_server(args=["--webhook-url", "http://localhost:8074/webhook"])
    def test_webhook_no_endpoint(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("Sending webhook to http://localhost:8074/webhook has failed", out)

    @HurricanServerTest.cycle_server(
        args=["--command", "failingcommand", "--webhook-url", "http://localhost:8074/webhook"]
    )
    def test_startup_failed_command_webhook_no_endpoint(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("Sending webhook to http://localhost:8074/webhook has failed", out)
        self.assertIn("Loop will be closed", out)

    @HurricanServerTest.cycle_server
    def test_duplicate_registration(self):
        from hurricane.metrics import registry
        from hurricane.metrics.requests import RequestCounterMetric

        try:
            registry.register(RequestCounterMetric)
        except Exception as e:
            exception = e
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("Metric ID (request_counter) is already registered.", str(exception))

    @HurricanServerTest.cycle_server
    def test_registration_metrics_wrong_key(self):
        class TestWrongKey:
            code = "test"

        from hurricane.metrics import registry

        registry.unregister(TestWrongKey)
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)

    @HurricanServerTest.cycle_server
    def test_stored_metric(self):
        from hurricane.metrics import registry
        from hurricane.metrics.base import StoredMetric
        from hurricane.metrics.exceptions import MetricIdAlreadyRegistered

        try:
            registry.register(StoredMetric)
        except MetricIdAlreadyRegistered:
            registry.unregister(StoredMetric)
            registry.register(StoredMetric)

        StoredMetric(code="new_stored_metric", initial="initial_value")
        StoredMetric.set("new_value")
        value = StoredMetric.get()
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("new_value", value)

    @HurricanServerTest.cycle_server
    def test_calculated_metric(self):
        from hurricane.metrics import registry
        from hurricane.metrics.base import CalculatedMetric

        registry.register(CalculatedMetric)
        CalculatedMetric(code="new_calculated_metric")
        CalculatedMetric.get_from_registry()
        with self.assertRaises(NotImplementedError):
            CalculatedMetric.get_value()
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)

    @HurricanServerTest.cycle_server
    def test_counter_metric(self):
        from hurricane.metrics import registry
        from hurricane.metrics.base import CounterMetric
        from hurricane.metrics.exceptions import MetricIdAlreadyRegistered

        try:
            registry.register(CounterMetric)
        except MetricIdAlreadyRegistered:
            registry.unregister(CounterMetric)
            registry.register(CounterMetric)

        CounterMetric.increment()
        CounterMetric.increment()
        CounterMetric.decrement()
        value = CounterMetric.get()
        self.assertEqual(1, value)
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)

    @HurricanServerTest.cycle_server
    def test_unregistering_metrics(self):
        from hurricane.metrics import registry
        from hurricane.metrics.requests import RequestCounterMetric

        registry.unregister(RequestCounterMetric)
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)

    @HurricanServerTest.cycle_server
    def test_duplicate_registration_webhooks(self):
        from hurricane.webhooks import webhook_registry
        from hurricane.webhooks.webhook_types import StartupWebhook

        m = webhook_registry.get(StartupWebhook.code)

        try:
            webhook_registry.register(StartupWebhook)
        except Exception as e:
            exception = e
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(m.code, out)
        self.assertIn(self.starting_message, out)
        self.assertIn("Webhook Code (startup) is already registered.", str(exception))

    @HurricanServerTest.cycle_server
    def test_registration_webhooks_wrong_key(self):
        class TestWrongKey:
            code = "test"

        from hurricane.webhooks import webhook_registry

        webhook_registry.unregister(TestWrongKey)
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)

    @HurricanServerTest.cycle_server
    def test_unregistering_webhooks(self):
        from hurricane.webhooks import webhook_registry
        from hurricane.webhooks.webhook_types import StartupWebhook

        webhook_registry.unregister(StartupWebhook)
        webhook_registry.register(StartupWebhook)
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)

    @HurricanServerTest.cycle_server
    def test_busy_port(self):
        with self.assertRaises(BusyPortException):
            hurricane_server = HurricaneServerDriver()
            hurricane_server.start_server()
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)

    @HurricanServerTest.cycle_server
    def test_not_readall(self):
        try:
            out, err = self.driver.get_output(read_all=False)
        except TypeError:
            out, err = self.driver.get_output(read_all=True)
            self.assertIn(self.starting_message, out)

    @HurricanServerTest.cycle_server(env={"DJANGO_SETTINGS_MODULE": "tests.testapp.settings_operational_error"})
    def test_django_operational_error(self):

        res = self.probe_client.get(self.alive_route)
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(res.status, 500)
        self.assertIn("database error", res.text)

    @HurricanServerTest.cycle_server(env={"DJANGO_SETTINGS_MODULE": "tests.testapp.settings_systemcheck_error"})
    def test_django_systemcheck_error(self):

        res = self.probe_client.get(self.alive_route)
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(res.status, 500)
        self.assertIn("django check error", res.text)

    @HurricanServerTest.cycle_server(
        env={"DJANGO_SETTINGS_MODULE": "tests.testapp.settings_operational_error"},
        args=["--webhook-url", "http://localhost:8074/webhook"],
    )
    def test_django_operational_error_webhook(self):

        res = self.probe_client.get(self.alive_route)
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(res.status, 500)
        self.assertIn("Sending webhook to http://localhost:8074/webhook has failed", out)

    @HurricanServerTest.cycle_server(args=["--check-migrations"])
    def test_check_migrations(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("Database was checked successfully", out)
        self.assertIn("No pending migrations", out)

    @HurricanServerTest.cycle_server(
        env={"DJANGO_SETTINGS_MODULE": "tests.testapp.settings_db_and_migrations"}, args=["--check-migrations"]
    )
    def test_db_and_migrations_error(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("Webhook with a status warning has been initiated", out)

    @HurricanServerTest.cycle_server(
        env={"DJANGO_SETTINGS_MODULE": "tests.testapp.settings_check_databases"}, args=["--check-migrations"]
    )
    def test_check_databases_error(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn("Database command execution has failed with Fake cursor execute exception", out)

    @HurricanServerTest.cycle_server(args=["--check-migrations"])
    def test_signal_handler(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        with self.assertRaises(SystemExit):
            signal_handler("signal", "frame")

    @HurricanServerTest.cycle_server(args=["--max-lifetime", "2"])
    def test_max_lifetime(self):
        self.app_client.get("/")
        self.app_client.get("/")
        res = self.probe_client.get(self.alive_route)
        self.assertEqual(res.status, 200)
        self.app_client.get("/")
        res = self.probe_client.get(self.alive_route)
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(res.status, 400)

    @HurricanServerTest.cycle_server(env={"DJANGO_SETTINGS_MODULE": "tests.testapp.settings_media"}, args=["--media"])
    def test_django_media(self):
        response = requests.get("http://localhost:8000/media/logo.png")
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Serving media files", out)

    @HurricanServerTest.cycle_server(args=["--pycharm-host", "127.0.0.1", "--pycharm-port", "1234"])
    def test_pycharm_debug_no_existing_host(self):
        res = self.probe_client.get(self.alive_route)
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(res.status, 200)
        self.assertIn("Could not connect to 127.0.0.1: 1234", out)

    @HurricanServerTest.cycle_server(args=["--pycharm-host", "127.0.0.1"])
    def test_pycharm_debug_no_port(self):
        res = self.probe_client.get(self.alive_route)
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(res.status, 200)
        self.assertIn(
            "No '--pycharm-port' was specified. The '--pycharm-host' option can "
            "only be used in combination with the '--pycharm-port' option. ",
            out,
        )

    def test_cycle_server_function_exception(self):
        with self.assertRaises(Exception):
            hurricane_server = HurricaneServerDriver()
            hurricane_server.start_server(args=["test_function"])

    @HurricanServerTest.cycle_server(args=["--autoreload", f"--static-watch={STATIC_PATH}"])
    def test_static_watch_option(self):
        res = self.probe_client.get(self.alive_route)
        self.assertEqual(res.status, 200)
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(f"Watching path {STATIC_PATH}", out)

    def test_static_watch(self):
        if not os.path.exists("static"):
            os.makedirs("static")
            os.makedirs("static/new")
            static_watch()
            os.rmdir("static/new")
            os.rmdir("static")
