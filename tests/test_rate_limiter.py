import io
import time

from django.test import SimpleTestCase, override_settings

from hurricane.server.gateway import HurricaneWSGIGateway
from hurricane.server.limiter import (
    RateLimiterEngine,
    TokenBucketLimiter,
    extract_client_ip,
    normalize_proxy_header,
)


class ClientIPExtractionTests(SimpleTestCase):
    def test_x_forwarded_for_leftmost_client_ip(self):
        environ = {
            "HTTP_X_FORWARDED_FOR": "203.0.113.195, 70.41.3.18, 150.172.238.178",
            "REMOTE_ADDR": "10.42.0.1",
        }
        ip = extract_client_ip(environ, proxy_header="HTTP_X_FORWARDED_FOR")
        self.assertEqual(ip, "203.0.113.195")

    def test_x_real_ip_fallback(self):
        environ = {
            "HTTP_X_REAL_IP": "198.51.100.42",
            "REMOTE_ADDR": "10.42.0.1",
        }
        ip = extract_client_ip(environ, proxy_header="HTTP_X_FORWARDED_FOR")
        self.assertEqual(ip, "198.51.100.42")

    def test_remote_addr_fallback_when_no_headers(self):
        environ = {
            "REMOTE_ADDR": "127.0.0.1",
        }
        ip = extract_client_ip(environ, proxy_header="HTTP_X_FORWARDED_FOR")
        self.assertEqual(ip, "127.0.0.1")

    def test_unknown_fallback(self):
        environ = {}
        ip = extract_client_ip(environ)
        self.assertEqual(ip, "unknown")

    def test_normalize_proxy_header(self):
        self.assertEqual(normalize_proxy_header("X-Forwarded-For"), "HTTP_X_FORWARDED_FOR")
        self.assertEqual(normalize_proxy_header("HTTP_X_FORWARDED_FOR"), "HTTP_X_FORWARDED_FOR")
        self.assertEqual(normalize_proxy_header("x-real-ip"), "HTTP_X_REAL_IP")
        self.assertEqual(normalize_proxy_header("REMOTE_ADDR"), "REMOTE_ADDR")


class TokenBucketLimiterTests(SimpleTestCase):
    def test_token_bucket_burst_and_refill(self):
        # 4 req/sec, burst 3
        limiter = TokenBucketLimiter(rate=4.0, burst=3.0)
        client_ip = "192.0.2.1"

        # 3 initial tokens in bucket
        self.assertTrue(limiter.allow(client_ip))
        self.assertTrue(limiter.allow(client_ip))
        self.assertTrue(limiter.allow(client_ip))

        # 4th immediate request exceeds burst
        self.assertFalse(limiter.allow(client_ip))

        # Wait 0.3s -> adds ~1.2 tokens -> allows 1 request
        time.sleep(0.3)
        self.assertTrue(limiter.allow(client_ip))
        self.assertFalse(limiter.allow(client_ip))

    def test_independent_ip_tracking(self):
        limiter = TokenBucketLimiter(rate=1.0, burst=1.0)
        # IP 1 uses token
        self.assertTrue(limiter.allow("1.1.1.1"))
        self.assertFalse(limiter.allow("1.1.1.1"))

        # IP 2 has separate bucket
        self.assertTrue(limiter.allow("2.2.2.2"))
        self.assertFalse(limiter.allow("2.2.2.2"))

    def test_pruning_bounds_memory(self):
        limiter = TokenBucketLimiter(rate=1.0, burst=1.0, max_tracked_ips=10)
        for i in range(25):
            limiter.allow(f"10.0.0.{i}")
        # Pruning keeps bucket map bounded
        self.assertLessEqual(len(limiter._buckets), 15)


class RateLimiterEngineConfigTests(SimpleTestCase):
    def test_default_options(self):
        engine = RateLimiterEngine.from_options({})
        self.assertIsNotNone(engine)
        self.assertEqual(engine.rate, 10.0)  # type: ignore
        self.assertEqual(engine.burst, 30.0)  # type: ignore
        self.assertEqual(engine.proxy_header, "HTTP_X_FORWARDED_FOR")  # type: ignore

    def test_cli_custom_rate_and_burst(self):
        engine = RateLimiterEngine.from_options(
            {
                "rate_limit": "25/s",
                "rate_limit_burst": 50,
                "rate_limit_proxy_header": "X-Real-IP",
            }
        )
        self.assertIsNotNone(engine)
        self.assertEqual(engine.rate, 25.0)  # type: ignore
        self.assertEqual(engine.burst, 50.0)  # type: ignore
        self.assertEqual(engine.proxy_header, "HTTP_X_REAL_IP")  # type: ignore

    def test_disabled_via_cli_flags(self):
        self.assertIsNone(RateLimiterEngine.from_options({"no_rate_limit": True}))
        self.assertIsNone(RateLimiterEngine.from_options({"rate_limit": "off"}))

    @override_settings(HURRICANE_RATE_LIMIT=False)
    def test_disabled_via_django_settings(self):
        self.assertIsNone(RateLimiterEngine.from_options({}))

    @override_settings(HURRICANE_RATE_LIMIT={"ENABLED": True, "RATE": 5.0, "BURST": 15})
    def test_custom_django_settings(self):
        engine = RateLimiterEngine.from_options({})
        self.assertIsNotNone(engine)
        self.assertEqual(engine.rate, 5.0)  # type: ignore
        self.assertEqual(engine.burst, 15.0)  # type: ignore


class RateLimiterGatewayIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.gateway = HurricaneWSGIGateway(
            options={
                "rate_limit": "2/s",
                "rate_limit_burst": 2,
                "rate_limit_proxy_header": "X-Forwarded-For",
                "no_fast_404": True,
                "include_probe": True,
            }
        )

    def _call(self, path: str, ip: str = "192.168.1.100"):
        environ = {
            "PATH_INFO": path,
            "REQUEST_METHOD": "GET",
            "HTTP_X_FORWARDED_FOR": ip,
            "REMOTE_ADDR": "10.0.0.1",
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

    def test_gateway_enforces_rate_limit_silently(self):
        client_ip = "192.168.50.1"

        # Request 1 & 2 succeed (burst = 2)
        status1, _, body1 = self._call("/", ip=client_ip)
        self.assertEqual(status1, "200 OK")
        self.assertIn(b"Hello world!", body1)

        status2, _, body2 = self._call("/", ip=client_ip)
        self.assertEqual(status2, "200 OK")

        # Request 3 exceeds limit -> 429 Too Many Requests
        status3, headers3, body3 = self._call("/", ip=client_ip)
        self.assertEqual(status3, "429 Too Many Requests")
        self.assertIn(b"Too Many Requests", body3)
        headers_dict = dict(headers3)
        self.assertIn("Retry-After", headers_dict)

        # Another client IP is NOT affected
        other_status, _, other_body = self._call("/", ip="192.168.50.2")
        self.assertEqual(other_status, "200 OK")
        self.assertIn(b"Hello world!", other_body)

    def test_gateway_probes_are_never_rate_limited(self):
        from hurricane.metrics.requests import StartupTimeMetric

        StartupTimeMetric.set(1.0)
        spammer_ip = "192.168.99.1"
        # Exhaust tokens on application endpoint
        self._call("/", ip=spammer_ip)
        self._call("/", ip=spammer_ip)
        app_status, _, _ = self._call("/", ip=spammer_ip)
        self.assertEqual(app_status, "429 Too Many Requests")

        # Probe endpoints remain accessible
        status_startup, _, body_startup = self._call("/startup", ip=spammer_ip)
        self.assertEqual(status_startup, "200 OK")
        self.assertIn(b"Startup was finished", body_startup)
