import re

from hurricane.testing import HurricanServerTest


class HurricanStartServerTests(HurricanServerTest):
    @HurricanServerTest.cylce_server
    def test_default_startup(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("Starting a Tornado-powered Django web server on port 8000", out)
        self.assertIn("Probe application running on port 8001 with route /alive", out)

    @HurricanServerTest.cylce_server(args=["--port", "8085"])
    def test_port_startup(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("Starting a Tornado-powered Django web server on port 8085", out)
        self.assertIn("Probe application running on port 8086 with route /alive", out)

    @HurricanServerTest.cylce_server(args=["--startup-probe", "probe", "--probe-port", "8090"])
    def test_probe_startup(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("Starting a Tornado-powered Django web server on port 8000", out)
        self.assertIn("Probe application running on port 8090 with route", out)
        res = self.probe_client.get("/probe")
        self.assertEqual(res.status, 200)
        res = self.probe_client.post("/probe", data=None)
        self.assertEqual(res.status, 200)

    @HurricanServerTest.cylce_server(args=["--startup-probe", "probe", "--probe-port", "8000", "--port", "8000"])
    def test_probe_integrated_startup(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("Starting a Tornado-powered Django web server on port 8000", out)
        self.assertIn("running integrated on port 8000", out)
        res = self.probe_client.get("/probe")
        self.assertEqual(res.status, 200)

    @HurricanServerTest.cylce_server(args=["--no-metrics", "--probe-port", "8090"])
    def test_nometrics_startup(self):
        res = self.probe_client.get("/alive")
        self.assertEqual(res.status, 200)
        self.assertIn("alive", res.text)

    @HurricanServerTest.cylce_server
    def test_request(self):
        res = self.app_client.get("/")
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(res.status, 200)
        self.assertIn("200 GET / ", out)
        self.assertIn("Hello world", res.text)

    @HurricanServerTest.cylce_server(args=["--static", "--media"])
    def test_serve_statics_and_media(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("Starting a Tornado-powered Django web server on port 8000", out)
        self.assertIn("Probe application running on port 8001 with route /alive", out)

    @HurricanServerTest.cylce_server
    def test_metrics_request(self):
        self.app_client.get("/")
        res = self.probe_client.get("/alive")
        self.assertEqual(res.status, 200)
        self.assertIn("Average response time:", res.text)

    def _get_timing_from_string(self, string: str) -> str:
        m = re.compile(r"(?P<value>[0-9]*\.[0-9]{2})ms")
        match = m.search(string)
        if match:
            return match.group("value")

    @HurricanServerTest.cylce_server
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
        res = self.probe_client.get("/alive")

        timing = float(self._get_timing_from_string(res.text))
        self.assertEqual(res.status, 200)
        self.assertAlmostEqual(result, timing, 1)

    @HurricanServerTest.cylce_server
    def test_log_outputs(self):
        out, err = self.driver.get_output(read_all=True)
        res = self.app_client.get("/doesnotexist")
        self.assertEqual(res.status, 404)
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(" 404 GET /doesnotexist", out)
        res = self.app_client.get("/")
        self.assertEqual(res.status, 200)

    @HurricanServerTest.cylce_server
    def test_head_request(self):
        res = self.app_client.head("/")
        self.assertEqual(res.status, 200)
        self.assertEqual(res.text, "")

    @HurricanServerTest.cylce_server(args=["--command", "compilemessages", "--probe-port", "8090"])
    def test_startup_with_single_management_command(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("Starting a Tornado-powered Django web server on port 8000", out)
        self.assertIn("Probe application running on port 8090", out)
        self.assertIn("Started execution of management commands", out)
        self.assertIn("Started HTTP Server", out)

        res = self.probe_client.get("/startup")
        self.assertEqual(res.status, 200)
        res = self.probe_client.post("/startup", data=None)
        self.assertEqual(res.status, 200)
        res = self.app_client.get("/")
        self.assertEqual(res.status, 200)

    @HurricanServerTest.cylce_server(
        args=["--command", "makemigrations", "--command", "compilemessages", "--probe-port", "8090"]
    )
    def test_startup_with_multiple_management_commands(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("Starting a Tornado-powered Django web server on port 8000", out)
        self.assertIn("Probe application running on port 8090 with route", out)
        self.assertIn("Started execution of management commands", out)
        self.assertIn("No changes detected", out)
        self.assertIn("processing file", out)
        self.assertIn("Started HTTP Server", out)

        res = self.probe_client.get("/startup")
        self.assertEqual(res.status, 200)
        res = self.probe_client.post("/startup", data=None)
        self.assertEqual(res.status, 200)
        res = self.app_client.get("/")
        self.assertEqual(res.status, 200)

    @HurricanServerTest.cylce_server(args=["--command", "migrate", "--probe-port", "8090"])
    def test_startup_failing_management_command(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("Starting a Tornado-powered Django web server on port 8000", out)
        self.assertIn("Probe application running on port 8090 with route /alive", out)
        self.assertIn("Started execution of management commands", out)
        self.assertIn("ERROR", out)
