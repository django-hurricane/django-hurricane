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
        gateway = HurricaneASGIGateway(
            django_app=dummy_asgi_app,
            options={"fast_404": "prefix"},
            include_probe=False,
        )
        scope = {"type": "http", "path": "/wp-login.php", "method": "GET"}
        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {}

        await gateway(scope, receive, send)
        self.assertEqual(messages[0]["status"], 404)
        self.assertIn(b"Not Found", messages[1]["body"])

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
