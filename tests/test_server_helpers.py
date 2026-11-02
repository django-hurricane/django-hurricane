import os
import tempfile
import unittest
from unittest.mock import MagicMock

import granian._internal
from django.test import SimpleTestCase
from django.urls import include, path

from hurricane.management.commands.serve import _get_granian_target
from hurricane.metrics.base import StoredMetric
from hurricane.metrics.exceptions import MetricIdAlreadyRegistered
from hurricane.metrics.registry import MetricsRegistry
from hurricane.server import (
    HurricaneApplication,
    HurricaneProbeServer,
    _format_startup_commands,
    add_trailing_slash,
    make_http_server,
    make_probe_server,
    sanitize_probes,
    with_metrics,
)
from hurricane.server.fast_404 import extract_prefixes, prerender_404
from hurricane.server.limiter import (
    _is_rate_limiter_disabled,
    _parse_rate_value,
    normalize_proxy_header,
)


class ServerHelpersTests(SimpleTestCase):
    databases = {"default"}

    def test_with_metrics(self):
        self.assertTrue(with_metrics({}))
        self.assertTrue(with_metrics({"no_metrics": False}))
        self.assertFalse(with_metrics({"no_metrics": True}))

    def test_format_startup_commands(self):
        self.assertEqual(_format_startup_commands(None), "")
        self.assertEqual(_format_startup_commands([]), "")
        commands = [["migrate", "--noinput"], ["collectstatic"]]
        self.assertEqual(_format_startup_commands(commands), "migrate,--noinput,collectstatic")

    def test_sanitize_probes_and_trailing_slash(self):
        options = {
            "liveness_probe": "/alive",
            "readiness_probe": "/ready/",
            "startup_probe": "startup",
        }
        res_opts, representations = sanitize_probes(options)
        self.assertEqual(representations["liveness_probe"], "/alive")
        self.assertEqual(representations["readiness_probe"], "/ready/")
        self.assertEqual(representations["startup_probe"], "/startup")
        self.assertIn("{0,1}", res_opts["liveness_probe"])
        self.assertIn("{0,1}", res_opts["readiness_probe"])
        self.assertIn("{0,1}", res_opts["startup_probe"])

    def test_make_http_server_and_application_call(self):
        app = make_http_server(options={"no_metrics": True}, include_probe=False)
        self.assertIsInstance(app, HurricaneApplication)
        self.assertFalse(app.collect_metrics)

        # Test __call__ with dummy WSGI environ
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/",
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "8000",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": MagicMock(),
            "wsgi.errors": MagicMock(),
            "wsgi.multithread": True,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
        }
        status_headers = []

        def start_response(status, headers, exc_info=None):
            status_headers.append((status, headers))

        response = app(environ, start_response)
        self.assertIsNotNone(response)
        self.assertTrue(len(status_headers) > 0)

    def test_make_probe_server_and_stop(self):
        probe_server = make_probe_server(options={"port": 8000, "probe_port": 8001})
        self.assertIsInstance(probe_server, HurricaneProbeServer)
        # Calling stop before server is bound should not raise error
        probe_server.stop()

    def test_limiter_rate_parsing(self):
        self.assertIsNone(_parse_rate_value(None))
        self.assertIsNone(_parse_rate_value(True))
        self.assertIsNone(_parse_rate_value("auto"))
        self.assertIsNone(_parse_rate_value("invalid"))
        self.assertEqual(_parse_rate_value("10/s"), 10.0)
        self.assertEqual(_parse_rate_value("25/sec"), 25.0)
        self.assertEqual(_parse_rate_value(50), 50.0)

    def test_limiter_disabled_checks(self):
        dummy_settings = MagicMock()
        dummy_settings.HURRICANE_RATE_LIMIT_ENABLED = None
        dummy_settings.RATE_LIMIT_ENABLED = None
        dummy_settings.HURRICANE_RATE_LIMIT = None
        dummy_settings.RATE_LIMIT = None

        self.assertTrue(_is_rate_limiter_disabled({"no_rate_limit": True}, dummy_settings))
        self.assertTrue(_is_rate_limiter_disabled({"rate_limit": "off"}, dummy_settings))
        self.assertTrue(_is_rate_limiter_disabled({"rate_limit": "none"}, dummy_settings))
        self.assertFalse(_is_rate_limiter_disabled({}, dummy_settings))

        dummy_settings.HURRICANE_RATE_LIMIT_ENABLED = False
        self.assertTrue(_is_rate_limiter_disabled({}, dummy_settings))

    def test_limiter_proxy_header_normalization(self):
        self.assertEqual(normalize_proxy_header("X-Forwarded-For"), "HTTP_X_FORWARDED_FOR")
        self.assertEqual(normalize_proxy_header("HTTP_X_REAL_IP"), "HTTP_X_REAL_IP")
        self.assertEqual(normalize_proxy_header("cf-connecting-ip"), "HTTP_CF_CONNECTING_IP")

    def test_extract_prefixes_nested(self):
        subpatterns = [path("details/", lambda r: None)]
        urlpatterns = [
            path("nested/", include((subpatterns, "subapp"))),
            path("root/", lambda r: None),
        ]
        prefixes, has_catchall = extract_prefixes(urlpatterns, is_root=True)
        self.assertIn("nested", prefixes)
        self.assertIn("root", prefixes)
        self.assertFalse(has_catchall)

    def test_prerender_404(self):
        status, headers, body = prerender_404()
        self.assertEqual(status, "404 Not Found")
        self.assertIn(b"Not Found", body)

    def test_metrics_registry(self):
        reg = MetricsRegistry()

        class DummyMetric(StoredMetric):
            code = "dummy_test_metric"

        reg.register(DummyMetric)
        self.assertEqual(reg.get("dummy_test_metric").code, "dummy_test_metric")

        # Duplicate register raises exception
        with self.assertRaises(MetricIdAlreadyRegistered):
            reg.register(DummyMetric)

        # Unregister metric
        reg.unregister(DummyMetric)
        with self.assertRaises(KeyError):
            reg.get("dummy_test_metric")

        # Unregister non-existent metric should not raise
        reg.unregister(DummyMetric)

    def test_granian_target_resolution_in_app_directory(self):
        target = _get_granian_target()
        self.assertTrue(target.endswith(":get_application"))
        self.assertTrue(os.path.isabs(target.split(":")[0]))

        # Simulate running inside a directory named 'app' containing an __init__.py
        with tempfile.TemporaryDirectory() as tmpdir:
            app_dir = os.path.join(tmpdir, "app")
            os.makedirs(app_dir)
            with open(os.path.join(app_dir, "__init__.py"), "w") as f:
                f.write("")

            old_cwd = os.getcwd()
            try:
                os.chdir(app_dir)
                path, _ = granian._internal.get_import_components(target)
                resolved_module = granian._internal.prepare_import(path)
                self.assertEqual(resolved_module, "hurricane.server.granian")
            finally:
                os.chdir(old_cwd)

    def test_cgroups_cpu_detection_v2(self):
        from unittest.mock import mock_open, patch

        from hurricane.management.commands.serve import _get_container_cpu_count

        # Case 1: cgroup v2 with quota: 200000 100000 -> 2 CPUs
        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda p: p == "/sys/fs/cgroup/cpu.max"
            with patch("builtins.open", mock_open(read_data="200000 100000")):
                self.assertEqual(_get_container_cpu_count(), 2)

        # Case 2: cgroup v2 with "max 100000" -> falls back to os.cpu_count()
        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda p: p == "/sys/fs/cgroup/cpu.max"
            with patch("builtins.open", mock_open(read_data="max 100000")):
                self.assertEqual(_get_container_cpu_count(), os.cpu_count() or 1)

    def test_cgroups_cpu_detection_v1(self):
        from unittest.mock import mock_open, patch

        from hurricane.management.commands.serve import _get_container_cpu_count

        # Case 3: cgroup v1 with quota 150000 and period 100000 -> 2 CPUs (ceil)
        def fake_open(p, *args, **kwargs):
            if "cpu.cfs_quota_us" in p:
                return mock_open(read_data="150000").return_value
            if "cpu.cfs_period_us" in p:
                return mock_open(read_data="100000").return_value
            raise FileNotFoundError(p)

        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda p: "cpu.cfs_" in p
            with patch("builtins.open", side_effect=fake_open):
                self.assertEqual(_get_container_cpu_count(), 2)

        # Case 4: cgroup v1 with unconstrained quota -1 -> os.cpu_count()
        def fake_open_unconstrained(p, *args, **kwargs):
            if "cpu.cfs_quota_us" in p:
                return mock_open(read_data="-1").return_value
            raise FileNotFoundError(p)

        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda p: "cpu.cfs_quota_us" in p
            with patch("builtins.open", side_effect=fake_open_unconstrained):
                self.assertEqual(_get_container_cpu_count(), os.cpu_count() or 1)

    def test_command_setup_queue_limits(self):
        from hurricane.management.commands.serve import Command

        cmd = Command()
        # Explicit req_queue_len remains unchanged
        opts_explicit = {"req_queue_len_explicit": True, "req_queue_len": 42}
        cmd._setup_queue_limits(opts_explicit)
        self.assertEqual(opts_explicit["req_queue_len"], 42)

        # Non-explicit auto-calculates workers * 2
        opts_auto = {"req_queue_len_explicit": False, "workers": 8}
        cmd._setup_queue_limits(opts_auto)
        self.assertEqual(opts_auto["req_queue_len"], 16)

    def test_command_resolve_runtime_config(self):
        from hurricane.management.commands.serve import Command

        cmd = Command()
        # Explicit runtime threads
        self.assertEqual(cmd._resolve_runtime_threads({"runtime_threads": 6}, container_cpus=2), 6)
        # Default runtime threads capped at 4
        self.assertEqual(cmd._resolve_runtime_threads({}, container_cpus=8), 4)
        self.assertEqual(cmd._resolve_runtime_threads({}, container_cpus=1), 1)

        # Runtime mode resolution
        self.assertEqual(cmd._resolve_runtime_mode({"runtime_mode": "auto"}, runtime_threads=1), "st")
        self.assertEqual(cmd._resolve_runtime_mode({"runtime_mode": "auto"}, runtime_threads=4), "mt")
        self.assertEqual(cmd._resolve_runtime_mode({"runtime_mode": "st"}, runtime_threads=4), "st")

    def test_extract_client_ip_asgi_variations(self):
        from hurricane.server.limiter import extract_client_ip_asgi

        # Multiple IPs in X-Forwarded-For
        scope_forwarded = {"headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18, 150.172.238.178")]}
        self.assertEqual(extract_client_ip_asgi(scope_forwarded), "203.0.113.195")

        # X-Real-IP fallback
        scope_real_ip = {"headers": [(b"x-real-ip", b"198.51.100.42")]}
        self.assertEqual(extract_client_ip_asgi(scope_real_ip), "198.51.100.42")

        # Socket remote addr fallback
        scope_socket = {
            "client": ("192.0.2.1", 54321),
            "headers": [],
        }
        self.assertEqual(extract_client_ip_asgi(scope_socket), "192.0.2.1")

        # Completely unknown
        self.assertEqual(extract_client_ip_asgi({}), "unknown")

    def test_database_and_migration_helpers(self):
        from unittest.mock import MagicMock, patch

        # Database checks - test logic with mocked connections
        from django.db import connections

        from hurricane.server import command_task, count_migrations, static_watch

        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        def real_check_databases() -> bool:
            for db_name in connections:
                conn = connections[db_name]
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT (1)")
                    return True
                except Exception:
                    return False
            return True

        with patch.dict(connections, {"default": mock_conn}):
            self.assertTrue(real_check_databases())

            mock_conn.cursor.side_effect = Exception("DB error")
            self.assertFalse(real_check_databases())

        # Count migrations
        self.assertGreaterEqual(count_migrations(), 0)

        # Static watch
        with patch("hurricane.server.call_command") as mock_cmd:
            static_watch()
            mock_cmd.assert_called_once_with("collectstatic", interactive=False, clear=True)

        # Command task
        command_task(commands=[["check"]])

    def test_base_metrics_lifecycle(self):
        from hurricane.metrics import registry
        from hurricane.metrics.base import (
            AverageMetric,
            CalculatedMetric,
            CounterMetric,
            ObservedMetric,
            StoredMetric,
        )

        class TestCounter(CounterMetric):
            code = "test_counter_metric"

        class TestAverage(AverageMetric):
            code = "test_average_metric"

        class TestObserved(ObservedMetric):
            code = "test_observed_metric"

        class TestCalculated(CalculatedMetric):
            code = "test_calculated_metric"

            @classmethod
            def get_value(cls, instance):
                return 42

        registry.register(TestCounter)
        registry.register(TestAverage)
        registry.register(TestObserved)
        registry.register(TestCalculated)

        try:
            # Counter increment & decrement
            TestCounter.set(10)
            self.assertEqual(TestCounter.get(), 10)
            TestCounter.increment()
            self.assertEqual(TestCounter.get(), 11)
            TestCounter.decrement()
            self.assertEqual(TestCounter.get(), 10)

            # Average add_value
            TestAverage.set(0)
            TestAverage.add_value(10.0)
            TestAverage.add_value(20.0)
            self.assertAlmostEqual(TestAverage.get(), 15.0)

            # Observed observe
            TestObserved.observe(99.5)
            self.assertEqual(TestObserved.get(), 99.5)

            # Calculated get
            self.assertEqual(TestCalculated.get(), 42)
        finally:
            registry.unregister(TestCounter)
            registry.unregister(TestAverage)
            registry.unregister(TestObserved)
            registry.unregister(TestCalculated)

    def test_webhook_registry(self):
        from hurricane.webhooks.exceptions import WebhookCodeAlreadyRegistered
        from hurricane.webhooks.registry import WebhookRegistry

        class DummyWebhook:
            code = "dummy_webhook"

        reg = WebhookRegistry()
        reg.register(DummyWebhook)
        self.assertIsInstance(reg.get("dummy_webhook"), DummyWebhook)

        with self.assertRaises(WebhookCodeAlreadyRegistered):
            reg.register(DummyWebhook)

        reg.unregister(DummyWebhook)
        with self.assertRaises(KeyError):
            reg.get("dummy_webhook")

        # Unregistering non-existent webhook should not raise
        reg.unregister(DummyWebhook)
