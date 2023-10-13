from time import sleep

from prometheus_client.parser import text_string_to_metric_families

from hurricane.testing.testcases import HurricanServerTest


class HurricanStartServerTests(HurricanServerTest):
    metrics_route = "/metrics"
    starting_message = "Tornado-powered Django web server"
    starting_http_message = "Starting Prometheus metrics exporter on port "

    @HurricanServerTest.cycle_server
    def test_default_startup_with_prometheues(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn(
            "Starting probe application running on port 8001 with route liveness-probe: /alive, readiness-probe: /ready, startup-probe: /startup",
            out,
        )
        self.assertIn(self.starting_http_message, out)

    @HurricanServerTest.cycle_server(args=["--no-metrics"])
    def test_default_startup_without_prometheues(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_message, out)
        self.assertIn(
            "Starting probe application running on port 8001 with route liveness-probe: /alive, readiness-probe: /ready, startup-probe: /startup",
            out,
        )
        self.assertIn(
            "Running without Prometheus exporter, because --no-metrics flag was set",
            out,
        )
        res = self.probe_client.get(self.metrics_route)
        self.assertEqual(res.status, 404)

    @HurricanServerTest.cycle_server(args=["--probe-port", "8085"])
    def test_startup_port(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_http_message + "8085", out)

    @HurricanServerTest.cycle_server(args=["--probe-port", "8000"])
    def test_startup_integrated(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_http_message + "8000", out)

    @HurricanServerTest.cycle_server(args=["--probe-port", "8000", "--no-metrics"])
    def test_startup_integrated_no_exporter(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn("Running without Prometheus exporter, because", out)

    @HurricanServerTest.cycle_server(args=["--no-probe"])
    def test_startup_exporter_integrated_no_probe(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(
            "Running without Prometheus exporter, because --no-probe flag was set", out
        )

    @HurricanServerTest.cycle_server(args=["--metrics", "/metrics1"])
    def test_startup_path(self):
        out, err = self.driver.get_output(read_all=True)
        self.assertIn(self.starting_http_message + "8001 with route /metrics1", out)

    @HurricanServerTest.cycle_server()
    def test_export_families_len(self):
        res = self.probe_client.get(self.metrics_route)
        families = list(text_string_to_metric_families(res.text))
        self.assertEqual(len(families), 20)

    @HurricanServerTest.cycle_server()
    def test_exporter_request(self):
        res = self.probe_client.get(self.metrics_route)
        families = text_string_to_metric_families(res.text)
        for family in families:
            if family.name == "request_counter":
                self.assertEqual(len(family.samples), 1)  # zero requests
                self.assertEqual(family.samples[0].value, 0.0)
        # make a request
        res = self.app_client.get("/")
        # get the new metrics
        res = self.probe_client.get(self.metrics_route)
        families = text_string_to_metric_families(res.text)
        for family in families:
            if family.name == "request_counter":
                self.assertEqual(len(family.samples), 1)
                self.assertEqual(family.samples[0].value, 1.0)

    @HurricanServerTest.cycle_server()
    def test_exporter_path_requests(self):
        res = self.probe_client.get(self.metrics_route)
        families = text_string_to_metric_families(res.text)
        for family in families:
            if family.name == "path_requests":
                self.assertEqual(len(family.samples), 0)
        # make a request
        res = self.app_client.get("/")
        # get the new metrics
        res = self.probe_client.get(self.metrics_route)
        families = text_string_to_metric_families(res.text)
        for family in families:
            if family.name == "path_requests":
                self.assertEqual(len(family.samples), 1)
                self.assertEqual(family.samples[0].labels["method"], "GET")
                self.assertEqual(family.samples[0].labels["path"], "/")
                self.assertEqual(family.samples[0].value, 1)
        # make a second request
        res = self.app_client.get("/")
        res = self.app_client.get("/")
        res = self.app_client.get("/")
        # get the new metrics
        res = self.probe_client.get(self.metrics_route)
        families = text_string_to_metric_families(res.text)
        for family in families:
            if family.name == "path_requests":
                self.assertEqual(len(family.samples), 1)
                self.assertEqual(family.samples[0].labels["method"], "GET")
                self.assertEqual(family.samples[0].labels["path"], "/")
                self.assertEqual(family.samples[0].value, 4)
        res = self.app_client.get("/heavy")
        # get the new metrics
        res = self.probe_client.get(self.metrics_route)
        families = text_string_to_metric_families(res.text)
        for family in families:
            if family.name == "path_requests":
                self.assertEqual(len(family.samples), 2)
