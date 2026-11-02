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
            "/wp-admin/",
            "/wordpress/wp-admin/",
            "/.env",
            "/.env.production",
            "/.git/config",
            "/.git/HEAD",
            "/xmlrpc.php",
            "/phpmyadmin/index.php",
            "/cgi-bin/script.cgi",
            "/actuator/health",
            "/actuator/env",
            "/solr/admin",
            "/app.aspx",
            "/index.jsp",
            "/config.action",
            "/_ignition/execute-solution",
            "/telescope/requests",
            "/core/install.php",
            "/administrator/index.php",
            "/manager/html",
            "/package.json",
            "/database.yml",
            "/backup.sql.gz",
            "/elmah.axd",
            "/c99.php",
            "/phpinfo.php",
            "/de/wp-admin/",
            "/en/.env",
        ]
        for attack_path in attack_paths:
            drop = engine.should_drop(attack_path)
            self.assertIsNotNone(drop, f"Expected {attack_path} to be dropped")
            reason_type, detail = drop  # type: ignore
            self.assertEqual(reason_type, "signature")

        safe_paths = [
            "/",
            "/admin/",
            "/admin/login/",
            "/admin/auth/user/",
            "/medium",
            "/api/v1/users/",
            "/upload",
            "/media/test.png",
            "/static/css/style.css",
            "/.well-known/acme-challenge/token123",
            "/.well-known/openid-configuration",
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

    def test_on_demand_cache_keys_with_different_languages_and_hosts(self):
        engine = Fast404Engine(mode="signature")
        scope_de = {
            "type": "http",
            "path": "/de/wp-login.php",
            "scheme": "https",
            "headers": [(b"host", b"shop.mycompany.com:8443")],
        }
        key_de = engine.compute_cache_key_asgi(scope_de)
        self.assertEqual(key_de, "shop.mycompany.com:de:https")

        scope_en = {
            "type": "http",
            "path": "/en-us/.env",
            "scheme": "http",
            "headers": [(b"host", b"website.org")],
        }
        key_en = engine.compute_cache_key_asgi(scope_en)
        self.assertEqual(key_en, "website.org:en-us:http")

        # Independent cache storage per key
        engine.store_response(key_de, "404 Not Found", [("Content-Type", "text/html")], b"German 404")
        engine.store_response(key_en, "404 Not Found", [("Content-Type", "text/html")], b"English 404")

        self.assertEqual(engine.get_cached(key_de)[2], b"German 404")
        self.assertEqual(engine.get_cached(key_en)[2], b"English 404")


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
        self.assertIn(b"not found", body.lower())

        # Second call should be an immediate cache hit
        status2, headers2, body2 = self._call_gateway("/wp-login.php")
        self.assertEqual(status2, "404 Not Found")
        self.assertEqual(body2, body)

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

    @override_settings(FAST_404=False)
    def test_gateway_disabled_via_unprefixed_django_settings(self):
        disabled_gateway = HurricaneWSGIGateway(
            options={"no_probe": True},
        )
        self.assertIsNone(disabled_gateway.fast_404)

    @override_settings(
        FAST_404="prefix",
        FAST_404_PATTERNS=[r"\.custombak$"],
        FAST_404_EXTRA_PREFIXES=["unprefixed-custom-route"],
    )
    def test_gateway_unprefixed_custom_patterns_and_prefixes(self):
        gateway = HurricaneWSGIGateway(options={"no_probe": True})
        self.assertIsNotNone(gateway.fast_404)
        # Drop attack matching custom pattern
        self.assertIsNotNone(gateway.fast_404.should_drop("/secret.custombak"))
        # Allow route starting with extra prefix
        self.assertIsNone(gateway.fast_404.should_drop("/unprefixed-custom-route/data/"))

    def test_from_options_mode_off_and_log_drop(self):
        self.assertIsNone(Fast404Engine.from_options({"fast_404": "off"}))
        self.assertIsNone(Fast404Engine.from_options({"no_fast_404": True}))

        engine = Fast404Engine(mode="signature")
        # Ensure log_drop executes cleanly
        engine.log_drop({"REMOTE_ADDR": "1.2.3.4", "REQUEST_METHOD": "POST"}, "/.env", "signature", "/.env")

    @override_settings(
        ALLOWED_HOSTS=["production.mycompany.com", ".partner.org"],
        MIDDLEWARE=["django.middleware.common.CommonMiddleware"],
    )
    def test_prerender_404_with_strict_production_allowed_hosts(self):
        status, headers, body = prerender_404()
        self.assertEqual(status, "404 Not Found")
        self.assertIn(b"Not Found", body)

    def test_root_route_re_path_variations_not_dropped(self):
        import types

        from django.urls import include

        # 1. Direct path with empty string
        fake_mod_empty = types.ModuleType("fake_urls_empty")
        fake_mod_empty.urlpatterns = [path("", lambda r: None)]

        engine_empty = Fast404Engine(mode="prefix", urlconf=fake_mod_empty)
        self.assertIn("", engine_empty.valid_prefixes)
        self.assertIsNone(engine_empty.should_drop("/"))
        self.assertIsNone(engine_empty.should_drop(""))

        # 2. Included URLconf under empty string
        fake_mod_sub = types.ModuleType("fake_urls_sub")
        fake_mod_sub.urlpatterns = [path("dashboard/", lambda r: None)]

        fake_mod_inc = types.ModuleType("fake_urls_inc")
        fake_mod_inc.urlpatterns = [path("", include(fake_mod_sub))]

        engine_inc = Fast404Engine(mode="prefix", urlconf=fake_mod_inc)
        self.assertIn("", engine_inc.valid_prefixes)
        self.assertIn("dashboard", engine_inc.valid_prefixes)

        # 3. Test regex pattern re_path(r"^$")
        fake_mod_anchor = types.ModuleType("fake_urls_anchor")
        fake_mod_anchor.urlpatterns = [re_path(r"^$", lambda r: None)]

        engine_anchor = Fast404Engine(mode="prefix", urlconf=fake_mod_anchor)
        self.assertIn("", engine_anchor.valid_prefixes)
        self.assertIsNone(engine_anchor.should_drop("/"))

        # 4. Test regex pattern re_path(r"^/?$")
        fake_mod_optional = types.ModuleType("fake_urls_optional")
        fake_mod_optional.urlpatterns = [re_path(r"^/?$", lambda r: None)]

        engine_optional = Fast404Engine(mode="prefix", urlconf=fake_mod_optional)
        self.assertIn("", engine_optional.valid_prefixes)
        self.assertIsNone(engine_optional.should_drop("/"))

    def test_i18n_patterns_with_nested_cms_urls_and_root_route(self):
        import types

        from django.conf.urls.i18n import i18n_patterns
        from django.urls import include, path, re_path

        cms_mod = types.ModuleType("cms_urls")
        cms_mod.urlpatterns = [
            re_path(r"^(?P<slug>.*)$", lambda r, slug: None, name="pages-root"),
        ]

        filer_mod = types.ModuleType("filer_urls")
        filer_mod.urlpatterns = [
            path("canonical/", lambda r: None),
        ]

        portal_mod = types.ModuleType("portal_urls")
        portal_mod.urlpatterns = [path("", lambda r: None)]

        layouter_mod = types.ModuleType("layouter_urls")
        layouter_mod.urlpatterns = [path("", lambda r: None)]

        root_mod = types.ModuleType("root_urls")
        root_mod.urlpatterns = i18n_patterns(
            path("portal-static/", include((portal_mod, "portal"), namespace="portal")),
            path("layouter/", include((layouter_mod, "layouter"), namespace="layouter")),
            path("", include(filer_mod)),
            path("", include(cms_mod)),
        )

        engine = Fast404Engine(mode="auto", urlconf=root_mod)

        # 1. CMS root catchall must be detected, causing auto mode to switch to signature-only
        self.assertTrue(engine.has_root_catchall)
        self.assertEqual(engine.effective_mode, "signature")

        # 2. Both / and empty string must NOT be dropped
        self.assertIsNone(engine.should_drop("/"))
        self.assertIsNone(engine.should_drop(""))

        # 3. All valid application endpoints must NOT be dropped
        self.assertIsNone(engine.should_drop("/portal-static/"))
        self.assertIsNone(engine.should_drop("/layouter/"))
        self.assertIsNone(engine.should_drop("/canonical/"))
        self.assertIsNone(engine.should_drop("/my-dynamic-cms-page/"))

        # 4. Scanner attacks must still be dropped instantly!
        self.assertEqual(engine.should_drop("/wp-login.php"), ("signature", "/wp-login.php"))
        self.assertEqual(engine.should_drop("/.env"), ("signature", "/.env"))

    def test_re_path_unprefixed_mount_with_nested_frontpage_view(self):
        import types

        from django.urls import include, path, re_path
        from django.utils.translation import gettext_lazy as _

        shop_frontpage_mod = types.ModuleType("shop_frontpage_urls")
        shop_frontpage_mod.urlpatterns = [
            path("", lambda r: None, name="frontpage"),
        ]

        root_mod = types.ModuleType("shop_root_urls")
        root_mod.urlpatterns = [
            re_path(_(r"^"), include((shop_frontpage_mod, "frontpage"), namespace="frontpage")),
        ]

        engine = Fast404Engine(mode="auto", urlconf=root_mod)

        # 1. re_path(r'^') is an unprefixed mount that matches any incoming path, so has_root_catchall is True
        self.assertTrue(engine.has_root_catchall)
        self.assertEqual(engine.effective_mode, "signature")

        # 2. Both / and empty string must NOT be dropped
        self.assertIsNone(engine.should_drop("/"))
        self.assertIsNone(engine.should_drop(""))

        # 3. Scanner attacks must still be dropped
        self.assertEqual(engine.should_drop("/wp-login.php"), ("signature", "/wp-login.php"))
        self.assertEqual(engine.should_drop("/.env"), ("signature", "/.env"))

    def test_on_demand_fallthrough_and_caching(self):
        import asyncio

        from hurricane.server.gateway import HurricaneASGIGateway

        django_calls = 0

        async def fake_django(scope, receive, send):
            nonlocal django_calls
            django_calls += 1
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/html; charset=utf-8")],
                }
            )
            await send({"type": "http.response.body", "body": b"<html>Custom 404 from CMS</html>"})

        engine = Fast404Engine(mode="prefix")
        engine._cache.clear()

        gateway = HurricaneASGIGateway(django_app=fake_django, options={"no_fast_404": False})
        gateway.fast_404 = engine

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/unknown-prefix/page",
            "headers": [(b"host", b"shop.example.com")],
        }

        # 1. First request is a cache miss: falls through into Django!
        msgs1: list = []

        async def send1(m):
            msgs1.append(m)

        async def recv1():
            return {}

        asyncio.run(gateway(scope, recv1, send1))

        self.assertEqual(django_calls, 1)
        self.assertEqual(msgs1[0]["status"], 404)
        self.assertEqual(msgs1[1]["body"], b"<html>Custom 404 from CMS</html>")

        # 2. Second request is a cache hit: served from memory directly in microseconds!
        msgs2: list = []

        async def send2(m):
            msgs2.append(m)

        async def recv2():
            return {}

        asyncio.run(gateway(scope, recv2, send2))

        self.assertEqual(django_calls, 1)  # Django was NOT invoked a second time!
        self.assertEqual(msgs2[0]["status"], 404)
        self.assertEqual(msgs2[1]["body"], b"<html>Custom 404 from CMS</html>")

    def test_signature_attack_serves_cached_custom_404_when_cache_is_warm(self):
        import asyncio

        from hurricane.server.gateway import HurricaneASGIGateway

        django_calls = 0

        async def fake_django(scope, receive, send):
            nonlocal django_calls
            django_calls += 1
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/html; charset=utf-8")],
                }
            )
            await send({"type": "http.response.body", "body": b"<html>Custom CMS 404</html>"})

        engine = Fast404Engine(mode="signature")
        gateway = HurricaneASGIGateway(django_app=fake_django, options={"no_fast_404": False})
        gateway.fast_404 = engine

        scope_attack = {
            "type": "http",
            "method": "GET",
            "path": "/wp-admin/",
            "headers": [(b"host", b"shop.example.com")],
        }

        # 1. Cold cache: signature attack is dropped immediately with fallback HTML without touching Django
        msgs1: list = []

        async def send1(m):
            msgs1.append(m)

        async def recv1():
            return {}

        asyncio.run(gateway(scope_attack, recv1, send1))
        self.assertEqual(django_calls, 0)
        self.assertEqual(msgs1[0]["status"], 404)
        self.assertIn(b"Page Not Found", msgs1[1]["body"])

        # 2. Warm up the cache for this host & language
        cache_key = engine.compute_cache_key_asgi(scope_attack)
        engine.store_response(
            cache_key, "404 Not Found", [("Content-Type", "text/html; charset=utf-8")], b"<html>Custom CMS 404</html>"
        )

        # 3. Warm cache: signature attack is served the authentic custom rendered 404 content!
        msgs2: list = []

        async def send2(m):
            msgs2.append(m)

        asyncio.run(gateway(scope_attack, recv1, send2))
        self.assertEqual(django_calls, 0)  # Still 0 calls to Django!
        self.assertEqual(msgs2[0]["status"], 404)
        self.assertEqual(msgs2[1]["body"], b"<html>Custom CMS 404</html>")
