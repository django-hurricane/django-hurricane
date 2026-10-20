import os
import time

from django.test import SimpleTestCase

from hurricane.testing.drivers import HurricaneServerDriver


class HurricaneSettingsServerTest(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.server = None

    def tearDown(self):
        if self.server:
            try:
                self.server.stop_server()
            except Exception:
                pass
            self.server = None
        super().tearDown()

    def test_port_gets_read_from_env(self):
        self.server = HurricaneServerDriver()
        self.server._get_env()
        self.server.start_server(env={"HURRICANE_PORT": "12345"})

        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()

        self.assertIn("Starting HTTP Server on port 12345", out)

    def test_port_gets_read_from_settings(self):
        with open("tests/testapp/settings.py", "r") as f:
            old_settings_content = f.read()

        try:
            with open("tests/testapp/settings.py", "a") as f:
                f.write("\nPORT = 6572\n")

            self.server = HurricaneServerDriver()
            self.server.start_server()
            out, _ = self.server.get_output(read_all=True)
            self.server.stop_server()

            self.assertIn("Starting HTTP Server on port 6572", out)
        finally:
            with open("tests/testapp/settings.py", "w") as f:
                f.write(old_settings_content)

    def test_port_get_overwritten_by_cli_arg(self):
        self.server = HurricaneServerDriver()
        self.server.start_server(params=["--port", "9276"])
        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()
        self.assertIn("Starting HTTP Server on port 9276", out)

    def test_media_get_read_from_env(self):
        self.server = HurricaneServerDriver()
        self.server._get_env()
        self.server.start_server(env={"HURRICANE_MEDIA": "True"})

        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()

        self.assertIn("Serving media files under /media/", out)

    def test_media_get_read_from_settings(self):
        with open("tests/testapp/settings.py", "r") as f:
            old_settings_content = f.read()

        try:
            with open("tests/testapp/settings.py", "a") as f:
                f.write("\nMEDIA = True\n")

            self.server = HurricaneServerDriver()
            self.server.start_server()
            out, _ = self.server.get_output(read_all=True)
            self.server.stop_server()

            self.assertIn("Serving media files under /media/", out)
        finally:
            with open("tests/testapp/settings.py", "w") as f:
                f.write(old_settings_content)

    def test_media_get_overwritten_by_cli_arg(self):
        self.server = HurricaneServerDriver()
        self.server.start_server(params=["--media"])
        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()
        self.assertIn("Serving media files under /media/", out)

    def test_live_probe_read_from_env(self):
        self.server = HurricaneServerDriver()
        self.server._get_env()
        self.server.start_server(env={"HURRICANE_LIVENESS_PROBE": "/veryalive"})

        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()

        self.assertIn("with route liveness-probe: /veryalive", out)

    def test_live_probe_read_from_settings(self):
        with open("tests/testapp/settings.py", "r") as f:
            old_settings_content = f.read()

        try:
            with open("tests/testapp/settings.py", "a") as f:
                f.write('\nLIVENESS_PROBE = "/veryalive"\n')

            self.server = HurricaneServerDriver()
            self.server.start_server()
            out, _ = self.server.get_output(read_all=True)
            self.server.stop_server()

            self.assertIn("with route liveness-probe: /veryalive", out)
        finally:
            with open("tests/testapp/settings.py", "w") as f:
                f.write(old_settings_content)

    def test_live_probe_overwritten_by_cli_arg(self):
        self.server = HurricaneServerDriver()
        self.server.start_server(params=["--liveness-probe", "/veryalive"])
        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()
        self.assertIn("with route liveness-probe: /veryalive", out)
