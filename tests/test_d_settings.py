import os
import time

from django.test import SimpleTestCase, override_settings

from hurricane.server.loggers import STRUCTLOG_ENABLED
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

        if STRUCTLOG_ENABLED:
            self.assertIn("port=12345", out)
        else:
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

            if STRUCTLOG_ENABLED:
                self.assertIn("port=6572", out)
            else:
                self.assertIn("Starting HTTP Server on port 6572", out)
        finally:
            with open("tests/testapp/settings.py", "w") as f:
                f.write(old_settings_content)

    def test_port_get_overwritten_by_cli_arg(self):
        self.server = HurricaneServerDriver()
        self.server.start_server(params=["--port", "9276"])
        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()
        if STRUCTLOG_ENABLED:
            self.assertIn("port=9276", out)
        else:
            self.assertIn("Starting HTTP Server on port 9276", out)

    def test_media_get_read_from_env(self):
        self.server = HurricaneServerDriver()
        self.server._get_env()
        self.server.start_server(env={"HURRICANE_MEDIA": "True"})

        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()

        if STRUCTLOG_ENABLED:
            self.assertIn("Serving media", out)
            self.assertIn("prefix=/media/", out)
        else:
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

            if STRUCTLOG_ENABLED:
                self.assertIn("Serving media", out)
                self.assertIn("prefix=/media/", out)
            else:
                self.assertIn("Serving media files under /media/", out)
        finally:
            with open("tests/testapp/settings.py", "w") as f:
                f.write(old_settings_content)

    def test_media_get_overwritten_by_cli_arg(self):
        self.server = HurricaneServerDriver()
        self.server.start_server(params=["--media"])
        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()
        if STRUCTLOG_ENABLED:
            self.assertIn("Serving media", out)
            self.assertIn("prefix=/media/", out)
        else:
            self.assertIn("Serving media files under /media/", out)

    def test_live_probe_read_from_env(self):
        self.server = HurricaneServerDriver()
        self.server._get_env()
        self.server.start_server(env={"HURRICANE_LIVENESS_PROBE": "/veryalive"})

        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()

        if STRUCTLOG_ENABLED:
            self.assertIn("liveness=/veryalive", out)
        else:
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

            if STRUCTLOG_ENABLED:
                self.assertIn("liveness=/veryalive", out)
            else:
                self.assertIn("with route liveness-probe: /veryalive", out)
        finally:
            with open("tests/testapp/settings.py", "w") as f:
                f.write(old_settings_content)

    def test_live_probe_overwritten_by_cli_arg(self):
        self.server = HurricaneServerDriver()
        self.server.start_server(params=["--liveness-probe", "/veryalive"])
        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()
        if STRUCTLOG_ENABLED:
            self.assertIn("liveness=/veryalive", out)
        else:
            self.assertIn("with route liveness-probe: /veryalive", out)

    def test_port_gets_read_from_prefixed_settings(self):
        with open("tests/testapp/settings.py", "r") as f:
            old_settings_content = f.read()

        try:
            with open("tests/testapp/settings.py", "a") as f:
                f.write("\nHURRICANE_PORT = 6589\n")

            self.server = HurricaneServerDriver()
            self.server.start_server()
            out, _ = self.server.get_output(read_all=True)
            self.server.stop_server()

            if STRUCTLOG_ENABLED:
                self.assertIn("port=6589", out)
            else:
                self.assertIn("Starting HTTP Server on port 6589", out)
        finally:
            with open("tests/testapp/settings.py", "w") as f:
                f.write(old_settings_content)

    def test_port_gets_read_from_unprefixed_env(self):
        self.server = HurricaneServerDriver()
        self.server.start_server(env={"PORT": "6591"})
        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()

        if STRUCTLOG_ENABLED:
            self.assertIn("port=6591", out)
        else:
            self.assertIn("Starting HTTP Server on port 6591", out)

    def test_req_queue_len_warning_in_asgi_mode(self):
        self.server = HurricaneServerDriver()
        self.server.start_server(
            params=["--mode", "asgi", "--req-queue-len", "5", "--port", "8999", "--probe-port", "8999"]
        )
        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()

        self.assertIn("The '--req-queue-len' option", out)
        self.assertIn("ignored when running in ASGI mode", out)

    def test_mode_cli_argument(self):
        import argparse

        from hurricane.management.commands.serve import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)

        args = parser.parse_args(["--mode", "asgi"])
        self.assertEqual(args.mode, "asgi")

        # Legacy --interface flag alias
        legacy_args = parser.parse_args(["--interface", "wsgi"])
        self.assertEqual(legacy_args.mode, "wsgi")

    @override_settings(MODE="asgi")
    def test_mode_from_unprefixed_settings(self):
        import argparse

        from hurricane.management.commands.serve import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        options = vars(parser.parse_args([]))
        cmd.merge_options(options)
        self.assertEqual(options["mode"], "asgi")
        self.assertEqual(options["interface"], "asgi")

    @override_settings(HURRICANE_MODE="wsgi")
    def test_mode_from_prefixed_settings(self):
        import argparse

        from hurricane.management.commands.serve import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        options = vars(parser.parse_args([]))
        cmd.merge_options(options)
        self.assertEqual(options["mode"], "wsgi")
        self.assertEqual(options["interface"], "wsgi")

    @override_settings(INTERFACE="asgi")
    def test_mode_legacy_interface_setting_fallback(self):
        import argparse

        from hurricane.management.commands.serve import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        options = vars(parser.parse_args([]))
        cmd.merge_options(options)
        self.assertEqual(options["mode"], "asgi")
        self.assertEqual(options["interface"], "asgi")

    def test_runtime_threads_cli_argument(self):
        import argparse

        from hurricane.management.commands.serve import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        options = vars(parser.parse_args(["--runtime-threads", "8"]))
        cmd.merge_options(options)
        self.assertEqual(options["runtime_threads"], 8)

    @override_settings(HURRICANE_RUNTIME_THREADS=4)
    def test_runtime_threads_prefixed_setting(self):
        import argparse

        from hurricane.management.commands.serve import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        options = vars(parser.parse_args([]))
        cmd.merge_options(options)
        self.assertEqual(options["runtime_threads"], 4)

    @override_settings(RUNTIME_THREADS=6)
    def test_runtime_threads_unprefixed_setting(self):
        import argparse

        from hurricane.management.commands.serve import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        options = vars(parser.parse_args([]))
        cmd.merge_options(options)
        self.assertEqual(options["runtime_threads"], 6)

    def test_runtime_mode_cli_argument(self):
        import argparse

        from hurricane.management.commands.serve import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        options = vars(parser.parse_args(["--runtime-mode", "st"]))
        cmd.merge_options(options)
        self.assertEqual(options["runtime_mode"], "st")

    @override_settings(HURRICANE_RUNTIME_MODE="mt")
    def test_runtime_mode_prefixed_setting(self):
        import argparse

        from hurricane.management.commands.serve import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        options = vars(parser.parse_args([]))
        cmd.merge_options(options)
        self.assertEqual(options["runtime_mode"], "mt")

    @override_settings(RUNTIME_MODE="st")
    def test_runtime_mode_unprefixed_setting(self):
        import argparse

        from hurricane.management.commands.serve import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        options = vars(parser.parse_args([]))
        cmd.merge_options(options)
        self.assertEqual(options["runtime_mode"], "st")

    def test_container_cpu_detection_cgroup_v2(self):
        from unittest.mock import mock_open, patch

        from hurricane.management.commands.serve import _get_container_cpu_count

        # 2 cores quota: 200000 quota, 100000 period
        with patch("os.path.exists", side_effect=lambda path: path == "/sys/fs/cgroup/cpu.max"):
            with patch("builtins.open", mock_open(read_data="200000 100000")):
                self.assertEqual(_get_container_cpu_count(), 2)

    def test_container_cpu_detection_cgroup_v1(self):
        from unittest.mock import mock_open, patch

        from hurricane.management.commands.serve import _get_container_cpu_count

        def fake_exists(path):
            return path in ("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "/sys/fs/cgroup/cpu/cpu.cfs_period_us")

        def fake_open(path, *args, **kwargs):
            if "quota" in path:
                return mock_open(read_data="100000")()
            return mock_open(read_data="100000")()

        with patch("os.path.exists", side_effect=fake_exists):
            with patch("builtins.open", side_effect=fake_open):
                self.assertEqual(_get_container_cpu_count(), 1)

    def test_serve_in_asgi_mode_starts_cleanly(self):
        self.server = HurricaneServerDriver()
        self.server.start_server(params=["--mode", "asgi", "--no-probe", "--port", "8125"])
        out, _ = self.server.get_output(read_all=True)
        self.server.stop_server()

        self.assertIn("HTTP configured", out)
        self.assertIn("Runtime configuration", out)
        self.assertIn("mode=asgi", out)
        self.assertNotIn("ConfigurationError", out)
        self.assertNotIn("blocking_threads is undefined", out)
