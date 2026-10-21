from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from django.urls import path, re_path

from hurricane.server.fast_404 import (
    DEFAULT_ANTI_DJANGO_PATTERNS,
    Fast404Engine,
    extract_prefixes,
    prerender_404,
)
from hurricane.server.gateway import HurricaneWSGIGateway


class Fast404EngineTests(SimpleTestCase):
    def test_default_signature_matching(self):
        engine = Fast404Engine(mode="signature")

        attack_paths = [
            "/wp-login.php",
            "/wordpress/wp-admin/",
            "/.env",
            "/.env.production",
            "/.git/config",
            "/.git/HEAD",
            "/xmlrpc.php",
            "/phpmyadmin/index.php",
            "/cgi-bin/script.cgi",
            "/actuator/health",
            "/solr/admin",
            "/app.aspx",
            "/index.jsp",
            "/config.action",
        ]
        for attack_path in attack_paths:
            drop = engine.should_drop(attack_path)
            self.assertIsNotNone(drop, f"Expected {attack_path} to be dropped")
            reason_type, detail = drop  # type: ignore
            self.assertEqual(reason_type, "signature")

        safe_paths = [
            "/",
            "/medium",
            "/api/v1/users/",
            "/upload",
            "/media/test.png",
            "/static/css/style.css",
        ]
        for safe_path in safe_paths:
            drop = engine.should_drop(safe_path)
            self.assertIsNone(drop, f"Expected {safe_path} to be allowed")

    def test_prefix_extraction_standard_app(self):
        mock_patterns = [
            path("", lambda r: None),
            path("api/v1/", lambda r: None),
            path("admin/", lambda r: None),
            re_path(r"^auth/", lambda r: None),
        ]
        prefixes, has_catchall = extract_prefixes(mock_patterns, is_root=True)
        self.assertFalse(has_catchall)
        self.assertIn("", prefixes)
        self.assertIn("api", prefixes)
        self.assertIn("admin", prefixes)
        self.assertIn("auth", prefixes)

    def test_root_catchall_detection_cms(self):
        # 1. Path converter catchall
        cms_patterns_1 = [
            path("admin/", lambda r: None),
            path("<path:slug>/", lambda r: None),
        ]
        _, has_catchall_1 = extract_prefixes(cms_patterns_1, is_root=True)
        self.assertTrue(has_catchall_1)

        # 2. Regex catchall
        cms_patterns_2 = [
            path("admin/", lambda r: None),
            re_path(r"^.*$", lambda r: None),
        ]
        _, has_catchall_2 = extract_prefixes(cms_patterns_2, is_root=True)
        self.assertTrue(has_catchall_2)

    def test_auto_mode_falls_back_to_signature_on_catchall(self):
        cms_patterns = [
            path("admin/", lambda r: None),
            path("<path:slug>/", lambda r: None),
        ]
        with patch("django.urls.get_resolver") as mock_resolver:
            mock_resolver.return_value.url_patterns = cms_patterns
            engine = Fast404Engine(mode="auto")
            self.assertEqual(engine.effective_mode, "signature")
            self.assertTrue(engine.has_root_catchall)

            # Legitimate CMS slug is allowed
            self.assertIsNone(engine.should_drop("/about-us/company/"))
            # Scanner probe is dropped
            self.assertIsNotNone(engine.should_drop("/.env"))

    def test_custom_extra_patterns_and_prefixes(self):
        engine = Fast404Engine(
            mode="prefix",
            extra_patterns=[r"\.bak$"],
            extra_prefixes={"custom-route"},
        )
        # Extra signature blocked
        drop = engine.should_drop("/database.bak")
        self.assertIsNotNone(drop)
        self.assertEqual(drop[0], "signature")  # type: ignore

        # Extra prefix allowed
        self.assertIsNone(engine.should_drop("/custom-route/subpath/"))

    def test_prerender_404_output(self):
        status, headers, body = prerender_404()
        self.assertEqual(status, "404 Not Found")
        header_dict = dict(headers)
        self.assertIn("Content-Type", header_dict)
        self.assertTrue(len(body) > 0)
        self.assertIsInstance(body, bytes)

    def test_prerender_404_fallback_on_exception(self):
        with patch("django.urls.get_resolver", side_effect=RuntimeError("URLconf error")):
            status, headers, body = prerender_404()
            self.assertEqual(status, "404 Not Found")
            self.assertIn(b"Not Found", body)


class Fast404GatewayIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.gateway = HurricaneWSGIGateway(
            options={"fast_404": "auto", "no_probe": True},
        )

    def _call_gateway(self, path: str, method: str = "GET"):
        import io

        environ = {
            "PATH_INFO": path,
            "REQUEST_METHOD": method,
            "REMOTE_ADDR": "127.0.0.1",
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "8000",
            "wsgi.url_scheme": "http",
            "wsgi.input": io.BytesIO(b""),
        }
        status_capture = []
        headers_capture = []

        def start_response(status, headers, exc_info=None):
            status_capture.append(status)
            headers_capture.append(headers)

        body_iter = self.gateway(environ, start_response)
        body = b"".join(body_iter)
        return status_capture[0], headers_capture[0], body

    def test_gateway_drops_attack_signature_immediately(self):
        status, headers, body = self._call_gateway("/wp-login.php")
        self.assertEqual(status, "404 Not Found")
        self.assertIn(b"Not Found", body)

        status_env, _, body_env = self._call_gateway("/.env")
        self.assertEqual(status_env, "404 Not Found")

    def test_gateway_drops_unknown_prefix_in_prefix_mode(self):
        # In testapp, "unknown-prefix" is not registered in urlpatterns
        status, headers, body = self._call_gateway("/unknown-prefix/page")
        self.assertEqual(status, "404 Not Found")

    def test_gateway_allows_valid_routes(self):
        status, headers, body = self._call_gateway("/")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Hello world!", body)

        # Confirm fast_404 allows all registered routes
        self.assertIsNone(self.gateway.fast_404.should_drop("/"))
        self.assertIsNone(self.gateway.fast_404.should_drop("/medium"))
        self.assertIsNone(self.gateway.fast_404.should_drop("/upload"))

    def test_gateway_disabled_via_no_fast_404(self):
        disabled_gateway = HurricaneWSGIGateway(
            options={"no_fast_404": True, "no_probe": True},
        )
        self.assertIsNone(disabled_gateway.fast_404)

    @override_settings(HURRICANE_FAST_404=False)
    def test_gateway_disabled_via_django_settings(self):
        disabled_gateway = HurricaneWSGIGateway(
            options={"no_probe": True},
        )
        self.assertIsNone(disabled_gateway.fast_404)
