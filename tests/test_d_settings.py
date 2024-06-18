import os
import time
from django.test import SimpleTestCase
from hurricane.testing.drivers import HurricaneServerDriver


class HurricaneSettingsServerTest(SimpleTestCase):
    def test_port_gets_read_from_env(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server._get_env()
        hurricane_server.start_server(env={"HURRICANE_PORT": "12345"})

        out, _ = hurricane_server.get_output(read_all=True)

        hurricane_server.stop_server()

        self.assertIn("Starting HTTP Server on port 12345", out)

    def test_port_gets_read_from_settings(self):
        with open("tests/testapp/settings.py", "r") as f:
            old_settings_content = f.read()

        with open("tests/testapp/settings.py", "a") as f:
            f.write("\nPORT = 6572\n")

        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server()
        out, _ = hurricane_server.get_output(read_all=True)
        hurricane_server.stop_server()

        self.assertIn("Starting HTTP Server on port 6572", out)

        with open("tests/testapp/settings.py", "w") as f:
            f.write(old_settings_content)

    def test_port_get_overwritten_by_cli_arg(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(params=["--port", "9276"])
        out, _ = hurricane_server.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertIn("Starting HTTP Server on port 9276", out)

    def test_media_get_read_from_env(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server._get_env()
        hurricane_server.start_server(env={"HURRICANE_MEDIA": "True"})

        out, _ = hurricane_server.get_output(read_all=True)

        hurricane_server.stop_server()

        self.assertIn("Serving media files under /media/", out)

    def test_media_get_read_from_settings(self):
        with open("tests/testapp/settings.py", "r") as f:
            old_settings_content = f.read()

        with open("tests/testapp/settings.py", "a") as f:
            f.write("\nMEDIA = True\n")

        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server()
        out, _ = hurricane_server.get_output(read_all=True)
        hurricane_server.stop_server()

        self.assertIn("Serving media files under /media/", out)

        with open("tests/testapp/settings.py", "w") as f:
            f.write(old_settings_content)

    def test_media_get_overwritten_by_cli_arg(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(params=["--media"])
        out, _ = hurricane_server.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertIn("Serving media files under /media/", out)

    def test_live_probe_read_from_env(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server._get_env()
        hurricane_server.start_server(env={"HURRICANE_LIVENESS_PROBE": "/veryalive"})

        out, _ = hurricane_server.get_output(read_all=True)

        hurricane_server.stop_server()

        self.assertIn("with route liveness-probe: /veryalive", out)

    def test_live_probe_read_from_settings(self):
        with open("tests/testapp/settings.py", "r") as f:
            old_settings_content = f.read()

        with open("tests/testapp/settings.py", "a") as f:
            f.write("\nLIVENESS_PROBE = '/veryalive'\n")

        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server()
        out, _ = hurricane_server.get_output(read_all=True)
        hurricane_server.stop_server()

        self.assertIn("with route liveness-probe: /veryalive", out)

        with open("tests/testapp/settings.py", "w") as f:
            f.write(old_settings_content)

    def test_live_probe_overwritten_by_cli_arg(self):
        hurricane_server = HurricaneServerDriver()
        hurricane_server.start_server(params=["--liveness-probe", "/veryalive"])
        out, _ = hurricane_server.get_output(read_all=True)
        hurricane_server.stop_server()
        self.assertIn("with route liveness-probe: /veryalive", out)
