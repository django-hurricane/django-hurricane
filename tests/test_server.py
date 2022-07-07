import re

import requests

from hurricane.server import signal_handler, static_watch
from hurricane.testing import HurricanServerTest
from hurricane.testing.drivers import BusyPortException, HurricaneServerDriver


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

    @HurricanServerTest.cycle_server(args=["--autoreload", "--static-watch"])
    def test_static_watch_option(self):
        res = self.probe_client.get(self.alive_route)
        self.assertEqual(res.status, 200)

    def test_static_watch(self):
        import os

        if not os.path.exists("static"):
            os.makedirs("static")
            os.makedirs("static/new")
            static_watch()
            os.rmdir("static/new")
            os.rmdir("static")
