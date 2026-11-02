import unittest
from unittest.mock import MagicMock, patch

from hurricane.metrics import StartupTimeMetric
from hurricane.server.gateway import (
    DjangoHandler,
    HurricaneASGIGateway,
    HurricaneWSGIContainer,
    HurricaneWSGIGateway,
)


async def dummy_asgi_app(scope, receive, send):
    if scope["type"] == "http":
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"Hello ASGI!"})
    elif scope["type"] == "websocket":
        await send({"type": "websocket.accept"})


async def error_asgi_app(scope, receive, send):
    await send(
        {
            "type": "http.response.start",
            "status": 500,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"Internal Error"})


class HurricaneASGIGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        StartupTimeMetric.set(0.5)

    async def asyncTearDown(self):
        StartupTimeMetric.set(None)

    async def test_non_http_scope_forwarded_to_django(self):
        gateway = HurricaneASGIGateway(django_app=dummy_asgi_app, options={})
        scope = {"type": "websocket"}
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        await gateway(scope, receive, send)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["type"], "websocket.accept")

    async def test_liveness_probe_success(self):
        gateway = HurricaneASGIGateway(django_app=dummy_asgi_app, options={}, include_probe=True)
        scope = {"type": "http", "path": "/alive", "method": "GET"}
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        await gateway(scope, receive, send)
        self.assertEqual(messages[0]["status"], 200)
        self.assertTrue(messages[1]["body"] == b"alive" or b"Average response time" in messages[1]["body"])

    async def test_liveness_probe_not_started(self):
        StartupTimeMetric.set(None)
        gateway = HurricaneASGIGateway(django_app=dummy_asgi_app, options={}, include_probe=True)
        scope = {"type": "http", "path": "/alive", "method": "GET"}
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        await gateway(scope, receive, send)
        self.assertEqual(messages[0]["status"], 400)
        self.assertIn(b"Startup is not finished", messages[1]["body"])

    async def test_readiness_probe_success(self):
        gateway = HurricaneASGIGateway(
            django_app=dummy_asgi_app,
            options={},
            check_func=lambda **kwargs: [],
            include_probe=True,
        )
        scope = {"type": "http", "path": "/ready", "method": "GET"}
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        await gateway(scope, receive, send)
        self.assertEqual(messages[0]["status"], 200)
        self.assertIn(messages[1]["body"], (b"ready", b"OK"))

    async def test_startup_probe_success(self):
        gateway = HurricaneASGIGateway(django_app=dummy_asgi_app, options={}, include_probe=True)
        scope = {"type": "http", "path": "/startup", "method": "GET"}
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        await gateway(scope, receive, send)
        self.assertEqual(messages[0]["status"], 200)
        self.assertIn(b"Startup was finished", messages[1]["body"])

    async def test_metrics_endpoint(self):
        gateway = HurricaneASGIGateway(
            django_app=dummy_asgi_app,
            options={"no_metrics": False},
            include_probe=True,
        )
        scope = {"type": "http", "path": "/metrics", "method": "GET"}
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        await gateway(scope, receive, send)
        self.assertEqual(messages[0]["status"], 200)
        self.assertIn(b"# TYPE", messages[1]["body"])

    async def test_probes_disabled_forward_to_django(self):
        gateway = HurricaneASGIGateway(django_app=dummy_asgi_app, options={"no_probe": True, "no_fast_404": True})
        scope = {"type": "http", "path": "/alive", "method": "GET"}
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        await gateway(scope, receive, send)
        self.assertEqual(messages[0]["status"], 200)
        self.assertEqual(messages[1]["body"], b"Hello ASGI!")

    async def test_fast_404_interception(self):
        async def not_found_asgi_app(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            await send({"type": "http.response.body", "body": b"Not Found"})

        gateway = HurricaneASGIGateway(
            django_app=not_found_asgi_app,
            options={"fast_404": "prefix"},
            include_probe=False,
        )
        scope = {"type": "http", "path": "/wp-login.php", "method": "GET"}
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        # 1. First request falls through to app, captures, and caches
        await gateway(scope, receive, send)
        self.assertEqual(messages[0]["status"], 404)
        self.assertIn(b"Not Found", messages[1]["body"])

        # 2. Second request is an instant Fast-404 cache hit
        messages2 = []

        async def send2(msg):
            messages2.append(msg)

        await gateway(scope, receive, send2)
        self.assertEqual(messages2[0]["status"], 404)
        self.assertIn(b"Not Found", messages2[1]["body"])

    async def test_forward_standard_request(self):
        gateway = HurricaneASGIGateway(django_app=dummy_asgi_app, options={"no_fast_404": True}, include_probe=False)
        scope = {
            "type": "http",
            "path": "/api/test",
            "method": "POST",
            "client": ("10.0.0.1", 54321),
        }
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        await gateway(scope, receive, send)
        self.assertEqual(messages[0]["status"], 200)
        self.assertEqual(messages[1]["body"], b"Hello ASGI!")

    async def test_forward_error_request_logging(self):
        gateway = HurricaneASGIGateway(django_app=error_asgi_app, options={"no_fast_404": True}, include_probe=False)
        scope = {
            "type": "http",
            "path": "/api/broken",
            "method": "GET",
            "client": ("10.0.0.2", 12345),
        }
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        await gateway(scope, receive, send)
        self.assertEqual(messages[0]["status"], 500)

    def test_compatibility_aliases(self):
        self.assertIs(DjangoHandler, HurricaneWSGIGateway)
        self.assertIs(HurricaneWSGIContainer, HurricaneWSGIGateway)

    async def test_event_loop_lag_tracker_lifecycle(self):
        gateway = HurricaneASGIGateway(django_app=dummy_asgi_app, options={}, include_probe=True)
        self.assertIsNotNone(gateway.loop_lag_tracker)
        self.assertFalse(gateway.loop_lag_tracker.is_unhealthy())

        # Start tracking task
        gateway.loop_lag_tracker.ensure_running()
        self.assertIsNotNone(gateway.loop_lag_tracker._task)

        # Calling again does not spawn a second task
        old_task = gateway.loop_lag_tracker._task
        gateway.loop_lag_tracker.ensure_running()
        self.assertIs(gateway.loop_lag_tracker._task, old_task)

        # Stop tracker cleanly
        gateway.loop_lag_tracker.stop()
        self.assertIsNone(gateway.loop_lag_tracker._task)

    async def test_asgi_readiness_lag_failure(self):
        gateway = HurricaneASGIGateway(
            django_app=dummy_asgi_app,
            options={},
            check_func=lambda **kwargs: [],
            include_probe=True,
        )
        # Simulate high event loop lag (e.g. 300ms > 200ms threshold)
        gateway.loop_lag_tracker.current_lag_ms = 300.0
        self.assertTrue(gateway.loop_lag_tracker.is_unhealthy())

        status, body = gateway.evaluate_readiness()
        self.assertEqual(status, 400)
        self.assertIn(b"Event loop lag limit exceeded", body)

    async def test_asgi_rate_limiter_interception(self):
        gateway = HurricaneASGIGateway(
            django_app=dummy_asgi_app,
            options={"rate_limit": "1/s", "rate_limit_burst": 1, "no_fast_404": True},
            include_probe=False,
        )
        scope = {
            "type": "http",
            "path": "/",
            "method": "GET",
            "headers": [(b"x-forwarded-for", b"198.51.100.1")],
        }
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        # First request consumes token
        await gateway(scope, receive, send)
        self.assertEqual(messages[0]["status"], 200)

        # Immediate second request should be rejected with 429
        messages2 = []

        async def send2(msg):
            messages2.append(msg)

        await gateway(scope, receive, send2)
        self.assertEqual(messages2[0]["status"], 429)

    async def test_asgi_concurrency_gate_readiness_failure(self):
        gateway = HurricaneASGIGateway(
            django_app=dummy_asgi_app,
            options={"req_queue_len": 5},
            check_func=lambda **kwargs: [],
            include_probe=True,
        )
        with patch.object(type(gateway.async_backlog_tracker), "current_backlog", new=10):
            status, body = gateway.evaluate_readiness()
            self.assertEqual(status, 400)
            self.assertIn(b"Request queue limit exceeded", body)

    async def test_asgi_max_body_size_enforced(self):
        gateway = HurricaneASGIGateway(
            django_app=dummy_asgi_app,
            options={"max_body_size": 100},
            include_probe=False,
        )
        scope = {
            "type": "http",
            "path": "/upload",
            "method": "POST",
            "headers": [(b"content-length", b"500")],
        }

        async def send(msg):
            pass

        async def receive():
            return {}

        with self.assertRaises(ConnectionResetError):
            await gateway(scope, receive, send)

    async def test_asgi_static_serving(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            static_file = os.path.join(tmpdir, "test.css")
            with open(static_file, "w") as f:
                f.write("body { color: red; }")

            gateway = HurricaneASGIGateway(
                django_app=dummy_asgi_app,
                options={"static": True},
                include_probe=False,
            )
            gateway.static_enabled = True
            gateway.static_root = tmpdir
            gateway.static_url = "/static/"

            # 1. Valid file
            messages = []

            async def send(msg):
                messages.append(msg)

            async def receive():
                return {}

            scope = {"type": "http", "path": "/static/test.css", "method": "GET"}
            await gateway(scope, receive, send)
            self.assertEqual(messages[0]["status"], 200)
            self.assertEqual(messages[1]["body"], b"body { color: red; }")

            # 2. Non-existent file
            messages_404 = []

            async def send_404(msg):
                messages_404.append(msg)

            scope_404 = {"type": "http", "path": "/static/missing.css", "method": "GET"}
            await gateway(scope_404, receive, send_404)
            self.assertEqual(messages_404[0]["status"], 404)

            # 3. Directory traversal attempt
            messages_traversal = []

            async def send_traversal(msg):
                messages_traversal.append(msg)

            scope_traversal = {"type": "http", "path": "/static/../../etc/passwd", "method": "GET"}
            await gateway(scope_traversal, receive, send_traversal)
            self.assertEqual(messages_traversal[0]["status"], 404)

    async def test_asgi_static_serving_etag_and_304(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            static_file = os.path.join(tmpdir, "style.css")
            with open(static_file, "w") as f:
                f.write("body { margin: 0; }")

            gateway = HurricaneASGIGateway(
                django_app=dummy_asgi_app,
                options={"static": True},
                include_probe=False,
            )
            gateway.static_enabled = True
            gateway.static_root = tmpdir
            gateway.static_url = "/static/"

            msgs1: list = []

            async def send1(m):
                msgs1.append(m)

            async def recv():
                return {}

            scope1 = {"type": "http", "path": "/static/style.css", "method": "GET"}
            await gateway(scope1, recv, send1)
            self.assertEqual(msgs1[0]["status"], 200)
            headers1 = {k.lower(): v.decode() for k, v in msgs1[0]["headers"]}
            self.assertIn(b"etag", headers1)
            self.assertIn(b"last-modified", headers1)
            etag = headers1[b"etag"]

            msgs2: list = []

            async def send2(m):
                msgs2.append(m)

            scope2 = {
                "type": "http",
                "path": "/static/style.css",
                "method": "GET",
                "headers": [(b"if-none-match", etag.encode())],
            }
            await gateway(scope2, recv, send2)
            self.assertEqual(msgs2[0]["status"], 304)
            self.assertEqual(msgs2[1]["body"], b"")

    async def test_asgi_static_serving_finders_fallback(self):
        import tempfile

        from django.conf import settings
        from django.test import override_settings

        gateway = HurricaneASGIGateway(
            django_app=dummy_asgi_app,
            options={"static": True},
            include_probe=False,
        )
        gateway.static_enabled = True
        gateway.static_root = "/non/existent/static/root"
        gateway.static_url = "/static/"

        with override_settings(INSTALLED_APPS=list(settings.INSTALLED_APPS) + ["django.contrib.staticfiles"]):
            with patch("django.contrib.staticfiles.finders.find") as mock_find:
                with tempfile.NamedTemporaryFile(suffix=".css") as tmp:
                    tmp.write(b"/* finder css */")
                    tmp.flush()
                    mock_find.return_value = tmp.name

                    msgs: list = []

                    async def send(m):
                        msgs.append(m)

                    async def recv():
                        return {}

                    scope = {"type": "http", "path": "/static/custom/app.css", "method": "GET"}
                    await gateway(scope, recv, send)
                    self.assertEqual(msgs[0]["status"], 200)
                    self.assertEqual(msgs[1]["body"], b"/* finder css */")

    def test_wsgi_static_serving_finders_and_304(self):
        import os
        import tempfile

        from hurricane.server.gateway import HurricaneWSGIGateway

        with tempfile.TemporaryDirectory() as tmpdir:
            static_file = os.path.join(tmpdir, "style.css")
            with open(static_file, "w") as f:
                f.write("body { color: blue; }")

            gateway = HurricaneWSGIGateway(
                options={"static": True, "no_probe": True},
            )
            gateway.static_enabled = True
            gateway.static_root = tmpdir
            gateway.static_url = "/static/"

            res_status = []
            res_headers = []

            def sr(s, h):
                res_status.append(s)
                res_headers.append(dict(h))

            body = b"".join(
                gateway(
                    {
                        "PATH_INFO": "/static/style.css",
                        "REQUEST_METHOD": "GET",
                        "SERVER_NAME": "localhost",
                        "SERVER_PORT": "8000",
                    },
                    sr,
                )
            )
            self.assertEqual(res_status[0], "200 OK")
            self.assertEqual(body, b"body { color: blue; }")
            etag = res_headers[0]["ETag"]

            res_status304 = []

            def sr304(s, h):
                res_status304.append(s)

            body304 = b"".join(
                gateway(
                    {
                        "PATH_INFO": "/static/style.css",
                        "REQUEST_METHOD": "GET",
                        "SERVER_NAME": "localhost",
                        "SERVER_PORT": "8000",
                        "HTTP_IF_NONE_MATCH": etag,
                    },
                    sr304,
                )
            )
            self.assertEqual(res_status304[0], "304 Not Modified")
            self.assertEqual(body304, b"")

    async def test_asgi_media_serving(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            media_file = os.path.join(tmpdir, "avatar.png")
            with open(media_file, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\nfake-image-bytes")

            gateway = HurricaneASGIGateway(
                django_app=dummy_asgi_app,
                options={"media": True},
                include_probe=False,
            )
            gateway.media_enabled = True
            gateway.media_root = tmpdir
            gateway.media_url = "/media/"

            # 1. Valid media file returns 200 with image/png
            msgs1: list = []

            async def send1(m):
                msgs1.append(m)

            async def recv():
                return {}

            scope1 = {"type": "http", "path": "/media/avatar.png", "method": "GET"}
            await gateway(scope1, recv, send1)
            self.assertEqual(msgs1[0]["status"], 200)
            headers1 = {k.lower(): v.decode() for k, v in msgs1[0]["headers"]}
            self.assertEqual(headers1[b"content-type"], "image/png")
            self.assertEqual(msgs1[1]["body"], b"\x89PNG\r\n\x1a\nfake-image-bytes")
            etag = headers1[b"etag"]

            # 2. Conditional request returns 304
            msgs2: list = []

            async def send2(m):
                msgs2.append(m)

            scope2 = {
                "type": "http",
                "path": "/media/avatar.png",
                "method": "GET",
                "headers": [(b"if-none-match", etag.encode())],
            }
            await gateway(scope2, recv, send2)
            self.assertEqual(msgs2[0]["status"], 304)

            # 3. Missing media file returns 404
            msgs3: list = []

            async def send3(m):
                msgs3.append(m)

            scope3 = {"type": "http", "path": "/media/missing.png", "method": "GET"}
            await gateway(scope3, recv, send3)
            self.assertEqual(msgs3[0]["status"], 404)

            # 4. Directory traversal attempt returns 404
            msgs4: list = []

            async def send4(m):
                msgs4.append(m)

            scope4 = {"type": "http", "path": "/media/../../etc/passwd", "method": "GET"}
            await gateway(scope4, recv, send4)
            self.assertEqual(msgs4[0]["status"], 404)

    def test_run_custom_check_exceptions(self):
        from django.core.management.base import SystemCheckError
        from django.db.utils import OperationalError

        from hurricane.metrics import HealthMetric

        gateway = HurricaneASGIGateway(django_app=dummy_asgi_app, options={})

        # SystemCheckError
        with patch.object(gateway, "check_func", side_effect=SystemCheckError("System check failed")):
            status, body = gateway._run_custom_check("health", HealthMetric)
            self.assertEqual(status, 500)

        # OperationalError
        with patch.object(gateway, "check_func", side_effect=OperationalError("DB down")):
            status, body = gateway._run_custom_check("health", HealthMetric)
            self.assertEqual(status, 500)

        # Generic Exception
        with patch.object(gateway, "check_func", side_effect=ValueError("Unexpected")):
            status, body = gateway._run_custom_check("health", HealthMetric)
            self.assertEqual(status, 500)

    async def test_fast_wsgi_to_asgi_duplicate_header_limit(self):
        from hurricane.server.gateway import FastWsgiToAsgi

        def dummy_wsgi_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"WSGI response"]

        adapter = FastWsgiToAsgi(dummy_wsgi_app)
        self.assertTrue(hasattr(adapter, "duplicate_header_limit"))
        self.assertEqual(adapter.duplicate_header_limit, 100)

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "http_version": "1.1",
            "headers": [(b"host", b"localhost")],
        }
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {"type": "http.request", "body": b""}

        await adapter(scope, receive, send)
        self.assertEqual(messages[0]["status"], 200)
        self.assertEqual(messages[1]["body"], b"WSGI response")
