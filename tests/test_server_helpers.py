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
        status, headers, body = prerender_404(urlconf=None)
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
