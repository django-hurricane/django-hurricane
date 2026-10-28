import asyncio
import mimetypes
import os
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import SystemCheckError
from django.core.wsgi import get_wsgi_application
from django.db import connection
from django.db.utils import OperationalError
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from hurricane.management.commands import HURRICANE_DIST_VERSION
from hurricane.metrics import (
    HealthMetric,
    ReadinessMetric,
    RequestCounterMetric,
    RequestQueueLengthMetric,
    ResponseTimeAverageMetric,
    StartupTimeMetric,
    registry,
)
from hurricane.server.loggers import STRUCTLOG_ENABLED, access_log, logger

if STRUCTLOG_ENABLED:
    from structlog.contextvars import bind_contextvars

STARTUP_NOT_FINISHED_MESSAGE: bytes = b"Startup is not finished yet"
STATUS_200_OK: str = "200 OK"
ASGI_HTTP_RESPONSE_START: str = "http.response.start"
ASGI_HTTP_RESPONSE_BODY: str = "http.response.body"


class WorkerBacklogTracker:
    """
    Thread-safe and process-safe tracker of in-flight requests and queue backlog.
    """

    def __init__(self, max_threads: int):
        self.max_threads = max(1, max_threads)

    @contextmanager
    def track_request(self):
        from hurricane.metrics.shared import SharedMetrics

        SharedMetrics.track_request_start(self.max_threads)
        try:
            yield
        finally:
            SharedMetrics.track_request_end(self.max_threads)

    @property
    def current_backlog(self) -> int:
        from hurricane.metrics.shared import SharedMetrics

        return SharedMetrics.get_queue_length()


class AsyncConcurrencyGate:
    """
    Concurrency gate to limit active Django execution slots.
    Tracks waiting backlog and triggers readiness unready signal if queue exceeds limit.
    """

    def __init__(self, max_concurrency: int):
        self.max_concurrency = max(1, max_concurrency)
        self.semaphore = asyncio.Semaphore(self.max_concurrency)

    @contextmanager
    def _track_metric(self):
        from hurricane.metrics.shared import SharedMetrics

        SharedMetrics.track_request_start(self.max_concurrency)
        try:
            yield
        finally:
            SharedMetrics.track_request_end(self.max_concurrency)

    @asynccontextmanager
    async def track_request(self):
        with self._track_metric():
            async with self.semaphore:
                yield

    @property
    def current_backlog(self) -> int:
        from hurricane.metrics.shared import SharedMetrics

        return SharedMetrics.get_queue_length()


class EventLoopLagTracker:
    """
    Monitors event loop responsiveness for ASGI servers.
    Measures event loop scheduling lag in milliseconds.
    If loop lag exceeds lag_threshold_ms, the server is considered overloaded or starving.
    """

    def __init__(self, check_interval: float = 0.05, lag_threshold_ms: float = 200.0):
        self.check_interval = check_interval
        self.lag_threshold_ms = lag_threshold_ms
        self.current_lag_ms = 0.0
        self._task: Optional[asyncio.Task] = None

    def ensure_running(self) -> None:
        if self._task is None or self._task.done():
            try:
                loop = asyncio.get_running_loop()
                self._task = loop.create_task(self._monitor())
            except RuntimeError:
                pass

    async def _monitor(self) -> None:
        while True:
            t0 = time.perf_counter()
            await asyncio.sleep(self.check_interval)
            elapsed = time.perf_counter() - t0
            lag = max(0.0, (elapsed - self.check_interval) * 1000.0)
            self.current_lag_ms = lag

    def is_unhealthy(self) -> bool:
        return self.current_lag_ms > self.lag_threshold_ms

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None


class FastWsgiToAsgiInstance:
    """
    Instance handler for FastWsgiToAsgi.
    """

    pass


try:
    from asgiref.sync import sync_to_async
    from asgiref.wsgi import WsgiToAsgi, WsgiToAsgiInstance

    class FastWsgiToAsgiInstance(WsgiToAsgiInstance):  # type: ignore[no-redef]
        @sync_to_async(thread_sensitive=False)
        def run_wsgi_app(self, body):
            return super(FastWsgiToAsgiInstance, self.__class__).run_wsgi_app.__wrapped__(self, body)

    class FastWsgiToAsgi(WsgiToAsgi):
        """
        Custom ASGI adapter for WSGI applications that disables thread_sensitive=True
        so that synchronous Django requests can execute in parallel on a ThreadPoolExecutor
        instead of bottlenecking on a single shared background thread.
        """

        async def __call__(self, scope, receive, send):
            await FastWsgiToAsgiInstance(self.wsgi_application, self.duplicate_header_limit)(scope, receive, send)
except ImportError:

    class FastWsgiToAsgi:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise ImproperlyConfigured("asgiref is required for FastWsgiToAsgi")


class BaseHurricaneGateway:
    """
    Base gateway encapsulating protocol-agnostic probe evaluation,
    webhook lifecycle, protection (Fast-404 and Rate Limiter), and metric tracking.
    """

    def __init__(
        self,
        options: Optional[Dict[str, Any]] = None,
        check_func: Optional[Callable] = None,
        include_probe: bool = True,
    ):
        self.options = options or {}
        self.check_func = check_func
        self.include_probe = include_probe

        # Concurrency & backlog tracking
        threads = self.options.get("workers") or min(32, (os.cpu_count() or 1) + 4)
        self.backlog_tracker = WorkerBacklogTracker(max_threads=threads)
        self.req_queue_len = self.options.get("req_queue_len", 10)
        self.max_lifetime = self.options.get("max_lifetime")
        self.collect_metrics = not self.options.get("no_metrics", False)

        # Probe route paths
        self.liveness_path = self._normalize_path(self.options.get("liveness_probe", "/alive"))
        self.readiness_path = self._normalize_path(self.options.get("readiness_probe", "/ready"))
        self.startup_path = self._normalize_path(self.options.get("startup_probe", "/startup"))
        self.metrics_path = self._normalize_path(self.options.get("metrics_path", "/metrics"))
        self.webhook_url = self.options.get("webhook_url")

        # Static & Media
        self.static_enabled = bool(self.options.get("static"))
        self.media_enabled = bool(self.options.get("media"))
        self.static_url = getattr(settings, "STATIC_URL", "/static/") or "/static/"
        self.static_root = getattr(settings, "STATIC_ROOT", "") or ""
        self.media_url = getattr(settings, "MEDIA_URL", "/media/") or "/media/"
        self.media_root = getattr(settings, "MEDIA_ROOT", "") or ""

        # Initialize Fast-404 protection engine
        try:
            from hurricane.server.fast_404 import Fast404Engine

            self.fast_404 = Fast404Engine.from_options(self.options)
        except Exception as e:
            logger.warning(f"Could not initialize Fast-404 engine: {e}")
            self.fast_404 = None

        # Initialize Rate Limiter engine
        try:
            from hurricane.server.limiter import RateLimiterEngine

            self.rate_limiter = RateLimiterEngine.from_options(self.options)
        except Exception as e:
            logger.warning(f"Could not initialize Rate Limiter engine: {e}")
            self.rate_limiter = None

    def _normalize_path(self, path: str) -> str:
        clean = path.split("{")[0]
        if not clean.startswith("/"):
            clean = "/" + clean
        return clean.rstrip("/") or "/"

    def _matches_path(self, request_path: str, target_path: str) -> bool:
        if request_path == target_path:
            return True
        if target_path != "/" and request_path == f"{target_path}/":
            return True
        return False

    def evaluate_liveness(self) -> Tuple[int, bytes]:
        if not StartupTimeMetric.get():
            return 400, STARTUP_NOT_FINISHED_MESSAGE
        if self.max_lifetime and RequestCounterMetric.get() > self.max_lifetime:
            return 400, b"Max lifetime reached"

        status, body = self._run_custom_check("liveness", HealthMetric)
        if status == 200 and body == b"OK":
            if resp_avg := ResponseTimeAverageMetric.get():
                body = (
                    f"Average response time: {resp_avg:.2f}ms Request queue size: {RequestQueueLengthMetric.get()} Rx"
                ).encode("utf-8")
            else:
                body = b"alive"
        return status, body

    def evaluate_readiness(self) -> Tuple[int, bytes]:
        if not StartupTimeMetric.get():
            return 400, STARTUP_NOT_FINISHED_MESSAGE

        current_backlog = RequestQueueLengthMetric.get()
        if current_backlog >= self.req_queue_len:
            self._update_webhook_and_metric(ReadinessMetric, status_succeeded=False)
            return 400, b"Request queue limit exceeded"

        return self._run_custom_check("readiness", ReadinessMetric)

    def evaluate_startup(self) -> Tuple[int, bytes]:
        startup_time = StartupTimeMetric.get()
        if startup_time:
            return 200, f"Startup was finished {startup_time}".encode("utf-8")
        return 400, STARTUP_NOT_FINISHED_MESSAGE

    def evaluate_metrics(self) -> bytes:
        from hurricane.metrics.shared import SharedMetrics

        req_cnt = SharedMetrics.get_requests()
        if RequestCounterMetric.prometheus:
            try:
                current_prom = RequestCounterMetric.prometheus._value.get()
                if req_cnt > current_prom:
                    RequestCounterMetric.prometheus.inc(req_cnt - current_prom)
            except Exception:
                pass

        resp_avg = SharedMetrics.get_average_response_time()
        if ResponseTimeAverageMetric.prometheus and resp_avg:
            try:
                ResponseTimeAverageMetric.prometheus.set(resp_avg)
            except Exception:
                pass

        for _, metric in registry.metrics.items():
            try:
                metric.get()
            except Exception:
                pass

        return generate_latest()

    def _run_custom_check(self, tag: str, metric: Any) -> Tuple[int, bytes]:
        try:
            if self.check_func:
                self.check_func(tags=[tag], include_deployment_checks=True)
            if getattr(settings, "DATABASES", None):
                connection.ensure_connection()
            self._update_webhook_and_metric(metric, status_succeeded=True)
            return 200, b"OK"
        except SystemCheckError as e:
            self._update_webhook_and_metric(metric, status_succeeded=False)
            msg = f"django check error: {e}" if getattr(settings, "DEBUG", False) else "check error"
            return 500, msg.encode("utf-8")
        except OperationalError as e:
            self._update_webhook_and_metric(metric, status_succeeded=False)
            msg = f"django database error: {e}" if getattr(settings, "DEBUG", False) else "database error"
            return 500, msg.encode("utf-8")
        except Exception as e:
            self._update_webhook_and_metric(metric, status_succeeded=False)
            msg = f"error: {e}" if getattr(settings, "DEBUG", False) else "error"
            return 500, msg.encode("utf-8")

    def _update_webhook_and_metric(self, metric: Any, status_succeeded: bool):
        from hurricane.webhooks import LivenessWebhook, ReadinessWebhook
        from hurricane.webhooks.base import WebhookStatus

        webhook_cls = LivenessWebhook if metric == HealthMetric else ReadinessWebhook
        current_val = metric.get()

        if status_succeeded:
            if not current_val:
                metric.set(True)
                self._send_webhook(metric, webhook_cls, WebhookStatus.SUCCEEDED, metric_change=True)
        else:
            if current_val or current_val is None:
                metric.set(False)
                self._send_webhook(metric, webhook_cls, WebhookStatus.FAILED, metric_change=False)

    def _send_webhook(self, metric: Any, webhook_cls: Any, status: Any, metric_change: bool):
        if self.webhook_url:
            logger.info(
                f"{metric.code.capitalize()} metric changed to {metric_change}. "
                f"{webhook_cls.code.capitalize()} webhook with status {status} triggered"
            )
            webhook_cls().run(url=self.webhook_url, status=status)

    def _check_max_body_size(self, environ: Dict[str, Any]) -> None:
        max_body_size = self.options.get("max_body_size")
        if not max_body_size:
            return
        try:
            content_length = int(environ.get("CONTENT_LENGTH") or 0)
            if content_length > max_body_size:
                raise ConnectionResetError("Request body size exceeded max_body_size")
        except (ValueError, TypeError):
            pass

    def _check_max_body_size_asgi(self, scope: Dict[str, Any]) -> None:
        max_body_size = self.options.get("max_body_size")
        if not max_body_size:
            return
        try:
            for header_name, header_val in scope.get("headers", []):
                if header_name.lower() == b"content-length":
                    content_length = int(header_val)
                    if content_length > max_body_size:
                        raise ConnectionResetError("Request body size exceeded max_body_size")
        except (ValueError, TypeError):
            pass

    @staticmethod
    def _sanitize_header_value(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            return None
        return normalized_value


class HurricaneWSGIGateway(BaseHurricaneGateway):
    """
    Unified WSGI gateway wrapping Django, probes, metrics, statics, and access logging.
    """

    def __init__(
        self,
        django_app: Optional[Callable] = None,
        options: Optional[Dict[str, Any]] = None,
        check_func: Optional[Callable] = None,
        include_probe: bool = True,
    ):
        super().__init__(options=options, check_func=check_func, include_probe=include_probe)
        self.django_app = django_app or get_wsgi_application()

    def _try_handle_probe(
        self,
        environ: Dict[str, Any],
        start_response: Callable,
        path: str,
        start_time: float,
    ) -> Optional[Any]:
        if not self.include_probe or self.options.get("no_probe", False):
            return None
        if self._matches_path(path, self.liveness_path):
            status_code, body = self.evaluate_liveness()
            return self._send_probe_response(environ, start_response, status_code, body, start_time)
        if self._matches_path(path, self.readiness_path):
            status_code, body = self.evaluate_readiness()
            return self._send_probe_response(environ, start_response, status_code, body, start_time)
        if self._matches_path(path, self.startup_path):
            status_code, body = self.evaluate_startup()
            return self._send_probe_response(environ, start_response, status_code, body, start_time)
        return None

    def _try_handle_metrics(
        self,
        environ: Dict[str, Any],
        start_response: Callable,
        method: str,
        path: str,
        start_time: float,
    ) -> Optional[Any]:
        if not (self.collect_metrics and self._matches_path(path, self.metrics_path)):
            return None
        payload = self.evaluate_metrics()
        headers = [
            ("Content-Type", CONTENT_TYPE_LATEST),
            ("Content-Length", str(len(payload))),
            ("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"),
        ]
        start_response(STATUS_200_OK, headers)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_request(environ, method, path, 200, elapsed_ms, is_probe=True)
        return [payload]

    def _try_handle_static_or_media(
        self,
        environ: Dict[str, Any],
        start_response: Callable,
        path: str,
        start_time: float,
    ) -> Optional[Any]:
        if self.static_enabled and path.startswith(self.static_url):
            return self._handle_static_file(
                environ, start_response, path, self.static_url, self.static_root, start_time
            )
        if self.media_enabled and path.startswith(self.media_url):
            return self._handle_static_file(environ, start_response, path, self.media_url, self.media_root, start_time)
        return None

    def _try_handle_security_shield(
        self,
        environ: Dict[str, Any],
        start_response: Callable,
        path: str,
    ) -> Optional[Any]:
        if self.fast_404 and self.fast_404.should_drop(path):
            status, headers, body = self.fast_404.get_response()
            if self.collect_metrics:
                RequestCounterMetric.increment()
            start_response(status, headers)
            return [body]

        if self.rate_limiter and not self.rate_limiter.is_allowed(environ):
            status, headers, body = self.rate_limiter.get_response()
            if self.collect_metrics:
                RequestCounterMetric.increment()
            start_response(status, headers)
            return [body]

        return None

    def _forward_to_django(
        self,
        environ: Dict[str, Any],
        start_response: Callable,
        method: str,
        path: str,
        start_time: float,
    ) -> Any:
        status_container: List[str] = [STATUS_200_OK]
        headers_container: List[List[Tuple[str, str]]] = [[]]

        def custom_start_response(status: str, headers: List[Tuple[str, str]], exc_info=None):
            status_container[0] = status
            headers_container[0] = headers
            return start_response(status, headers, exc_info)

        with self.backlog_tracker.track_request():
            response_iter = self.django_app(environ, custom_start_response)

        try:
            status_code = int(status_container[0].split()[0])
        except (ValueError, IndexError):
            status_code = 200

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_request(environ, method, path, status_code, elapsed_ms, is_probe=False)

        if self.collect_metrics:
            RequestCounterMetric.increment()
            ResponseTimeAverageMetric.add_value(elapsed_ms)

        return response_iter

    def __call__(self, environ: Dict[str, Any], start_response: Callable) -> Any:
        path = environ.get("PATH_INFO", "")
        method = environ.get("REQUEST_METHOD", "GET")
        start_time = time.perf_counter()

        if probe_resp := self._try_handle_probe(environ, start_response, path, start_time):
            return probe_resp

        if metrics_resp := self._try_handle_metrics(environ, start_response, method, path, start_time):
            return metrics_resp

        if static_resp := self._try_handle_static_or_media(environ, start_response, path, start_time):
            return static_resp

        if security_resp := self._try_handle_security_shield(environ, start_response, path):
            return security_resp

        self._check_max_body_size(environ)

        return self._forward_to_django(environ, start_response, method, path, start_time)

    def _send_probe_response(
        self,
        environ: Dict[str, Any],
        start_response: Callable,
        status_code: int,
        body: bytes,
        start_time: float,
    ) -> List[bytes]:
        status_str = f"{status_code} {'OK' if status_code == 200 else 'Bad Request' if status_code == 400 else 'Internal Server Error'}"
        headers = [
            ("Content-Type", "text/plain"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"),
        ]
        start_response(status_str, headers)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_request(
            environ,
            environ.get("REQUEST_METHOD", "GET"),
            environ.get("PATH_INFO", ""),
            status_code,
            elapsed_ms,
            is_probe=True,
        )
        return [body]

    def _handle_static_file(
        self,
        environ: Dict[str, Any],
        start_response: Callable,
        request_path: str,
        url_prefix: str,
        root_dir: str,
        start_time: float,
    ) -> List[bytes]:
        relative_path = request_path[len(url_prefix) :].lstrip("/")
        file_path = os.path.abspath(os.path.join(root_dir, relative_path))

        # Directory traversal protection
        if not file_path.startswith(os.path.abspath(root_dir)) or not os.path.isfile(file_path):
            headers = [("Content-Type", "text/plain"), ("Content-Length", "9")]
            start_response("404 Not Found", headers)
            return [b"Not Found"]

        content_type, _ = mimetypes.guess_type(file_path)
        content_type = content_type or "application/octet-stream"
        file_size = os.path.getsize(file_path)

        headers = [
            ("Content-Type", content_type),
            ("Content-Length", str(file_size)),
        ]
        start_response(STATUS_200_OK, headers)

        with open(file_path, "rb") as f:
            content = f.read()

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_request(
            environ,
            environ.get("REQUEST_METHOD", "GET"),
            request_path,
            200,
            elapsed_ms,
            is_probe=False,
        )
        return [content]

    def _log_request(
        self,
        environ: Dict[str, Any],
        method: str,
        path: str,
        status: int,
        elapsed_ms: float,
        is_probe: bool = False,
    ):
        if is_probe and not getattr(settings, "HURRICANE_LOG_PROBES", getattr(settings, "LOG_PROBES", False)):
            return

        if status < 400:
            log_method = access_log.info
        elif status < 500:
            log_method = access_log.warning
        else:
            log_method = access_log.error

        remote_ip = environ.get("HTTP_X_FORWARDED_FOR") or environ.get("REMOTE_ADDR") or "127.0.0.1"
        protocol = environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        request_id = environ.get("HTTP_X_REQUEST_ID", "n/a")
        traceparent = environ.get("HTTP_TRACEPARENT", "n/a")

        if STRUCTLOG_ENABLED:
            bind_contextvars(
                hurricane=HURRICANE_DIST_VERSION,
                protocol=protocol,
                method=method,
                path=path,
                status=status,
                request_time=elapsed_ms,
                remote_ip=remote_ip,
                id=request_id,
                traceparent=traceparent,
            )
            log_method(f"TX {method} {path} {round(elapsed_ms, 2)}ms")
        else:
            log_method(f"{status} {method} {path} ({remote_ip}) {elapsed_ms:.2f}ms")


class HurricaneASGIGateway(BaseHurricaneGateway):
    """
    Unified ASGI gateway wrapping Django, probes, metrics, statics, and access logging.
    """

    def __init__(
        self,
        django_app: Optional[Callable] = None,
        options: Optional[Dict[str, Any]] = None,
        check_func: Optional[Callable] = None,
        include_probe: bool = True,
    ):
        super().__init__(options=options, check_func=check_func, include_probe=include_probe)
        from django.core.asgi import get_asgi_application

        self.django_app = django_app or get_asgi_application()
        lag_threshold = float(
            self.options.get(
                "loop_lag_threshold",
                getattr(settings, "HURRICANE_LOOP_LAG_THRESHOLD", getattr(settings, "LOOP_LAG_THRESHOLD", 200.0)),
            )
        )
        self.loop_lag_tracker = EventLoopLagTracker(lag_threshold_ms=lag_threshold)

        threads = self.options.get("workers") or min(32, (os.cpu_count() or 1) + 4)
        self.async_backlog_tracker = AsyncConcurrencyGate(max_concurrency=threads)

    def evaluate_readiness(self) -> Tuple[int, bytes]:
        if not StartupTimeMetric.get():
            return 400, STARTUP_NOT_FINISHED_MESSAGE

        if self.loop_lag_tracker and self.loop_lag_tracker.is_unhealthy():
            self._update_webhook_and_metric(ReadinessMetric, status_succeeded=False)
            return (
                400,
                f"Event loop lag limit exceeded ({self.loop_lag_tracker.current_lag_ms:.1f}ms)".encode("utf-8"),
            )

        current_backlog = self.async_backlog_tracker.current_backlog
        if current_backlog >= self.req_queue_len:
            self._update_webhook_and_metric(ReadinessMetric, status_succeeded=False)
            return 400, f"Request queue limit exceeded ({current_backlog} queued)".encode("utf-8")

        return self._run_custom_check("readiness", ReadinessMetric)

    async def _evaluate_liveness_probe(self) -> Tuple[int, bytes]:
        from asgiref.sync import sync_to_async

        try:

            async def _check():
                async with self.async_backlog_tracker.track_request():
                    return await sync_to_async(self.evaluate_liveness, thread_sensitive=False)()

            return await asyncio.wait_for(_check(), timeout=0.9)
        except (asyncio.TimeoutError, TimeoutError):
            return 500, b"Liveness check timed out: worker deadlock detected"

    async def _try_handle_probe(self, scope: Dict[str, Any], send: Callable, path: str, start_time: float) -> bool:
        if not self.include_probe or self.options.get("no_probe", False):
            return False
        if self._matches_path(path, self.liveness_path):
            status, body = await self._evaluate_liveness_probe()
            await self._send_response(scope, send, status, body, start_time)
            return True
        if self._matches_path(path, self.readiness_path):
            from asgiref.sync import sync_to_async

            status, body = await sync_to_async(self.evaluate_readiness, thread_sensitive=False)()
            await self._send_response(scope, send, status, body, start_time)
            return True
        if self._matches_path(path, self.startup_path):
            status, body = self.evaluate_startup()
            await self._send_response(scope, send, status, body, start_time)
            return True
        return False

    async def _try_handle_metrics(self, scope: Dict[str, Any], send: Callable, path: str, start_time: float) -> bool:
        if not (self.collect_metrics and self._matches_path(path, self.metrics_path)):
            return False
        payload = self.evaluate_metrics()
        headers = [
            (b"content-type", CONTENT_TYPE_LATEST.encode("utf-8")),
            (b"content-length", str(len(payload)).encode("utf-8")),
            (b"cache-control", b"no-store, no-cache, must-revalidate, max-age=0"),
        ]
        await send({"type": ASGI_HTTP_RESPONSE_START, "status": 200, "headers": headers})
        await send({"type": ASGI_HTTP_RESPONSE_BODY, "body": payload})
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_asgi_request(scope, "GET", path, 200, elapsed_ms, is_probe=True)
        return True

    async def _try_handle_rate_limiter(self, scope: Dict[str, Any], send: Callable, start_time: float) -> bool:
        if not (self.rate_limiter and not self.rate_limiter.is_allowed_asgi(scope)):
            return False
        status_code, headers, body = self.rate_limiter.get_response()
        if self.collect_metrics:
            RequestCounterMetric.increment()
        try:
            status_code_int = int(status_code.split()[0])
        except (ValueError, IndexError, AttributeError):
            status_code_int = 429

        # Convert header list to bytes tuples for ASGI
        asgi_headers = [(k.encode("utf-8"), v.encode("utf-8")) for k, v in headers]
        await send({"type": ASGI_HTTP_RESPONSE_START, "status": status_code_int, "headers": asgi_headers})
        await send({"type": ASGI_HTTP_RESPONSE_BODY, "body": body})

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_asgi_request(
            scope, scope.get("method", "GET"), scope.get("path", ""), status_code_int, elapsed_ms, is_probe=False
        )
        return True

    async def _try_handle_fast_404(self, scope: Dict[str, Any], send: Callable, path: str, start_time: float) -> bool:
        if not (self.fast_404 and self.fast_404.should_drop(path)):
            return False
        _, _, body = self.fast_404.get_response()
        if self.collect_metrics:
            RequestCounterMetric.increment()
        await self._send_response(scope, send, 404, body, start_time, is_probe=False)
        return True

    async def _try_handle_static_or_media(
        self,
        scope: Dict[str, Any],
        send: Callable,
        path: str,
        start_time: float,
    ) -> bool:
        if self.static_enabled and path.startswith(self.static_url):
            await self._handle_static_file(scope, send, path, self.static_url, self.static_root, start_time)
            return True
        if self.media_enabled and path.startswith(self.media_url):
            await self._handle_static_file(scope, send, path, self.media_url, self.media_root, start_time)
            return True
        return False

    async def _handle_static_file(
        self,
        scope: Dict[str, Any],
        send: Callable,
        request_path: str,
        url_prefix: str,
        root_dir: str,
        start_time: float,
    ) -> None:
        from asgiref.sync import sync_to_async

        relative_path = request_path[len(url_prefix) :].lstrip("/")
        file_path = os.path.abspath(os.path.join(root_dir, relative_path))

        # Directory traversal protection
        is_safe = file_path.startswith(os.path.abspath(root_dir))
        is_file = await sync_to_async(os.path.isfile, thread_sensitive=False)(file_path) if is_safe else False

        if not is_safe or not is_file:
            await self._send_response(scope, send, 404, b"Not Found", start_time, is_probe=False)
            return

        content_type, _ = mimetypes.guess_type(file_path)
        content_type = content_type or "application/octet-stream"
        file_size = await sync_to_async(os.path.getsize, thread_sensitive=False)(file_path)

        headers = [
            (b"content-type", content_type.encode("utf-8")),
            (b"content-length", str(file_size).encode("utf-8")),
        ]
        await send({"type": ASGI_HTTP_RESPONSE_START, "status": 200, "headers": headers})

        def _read_file():
            with open(file_path, "rb") as f:
                return f.read()

        content = await sync_to_async(_read_file, thread_sensitive=False)()
        await send({"type": ASGI_HTTP_RESPONSE_BODY, "body": content})

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_asgi_request(
            scope,
            scope.get("method", "GET"),
            request_path,
            200,
            elapsed_ms,
            is_probe=False,
        )

    async def _forward_to_django(
        self,
        scope: Dict[str, Any],
        receive: Callable,
        send: Callable,
        method: str,
        path: str,
        start_time: float,
    ) -> None:
        status_code_container = [200]
        response_started = False

        async def logging_send(message: Mapping[str, Any]) -> None:
            nonlocal response_started
            if message["type"] == ASGI_HTTP_RESPONSE_START:
                response_started = True
                status_code_container[0] = int(message.get("status", 200))
            await send(message)

        try:
            await self.django_app(scope, receive, logging_send)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"Unhandled exception while processing {method} {path}: {e}",
                exc_info=True,
            )
            self._log_asgi_request(scope, method, path, 500, elapsed_ms, is_probe=False)
            if not response_started:
                await self._send_response(scope, send, 500, b"Internal Server Error", start_time, is_probe=False)
            return

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        if self.collect_metrics:
            RequestCounterMetric.increment()
            ResponseTimeAverageMetric.add_value(elapsed_ms)

        self._log_asgi_request(scope, method, path, status_code_container[0], elapsed_ms, is_probe=False)

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        if self.loop_lag_tracker:
            self.loop_lag_tracker.ensure_running()

        if scope["type"] != "http":
            await self.django_app(scope, receive, send)
            return

        self._check_max_body_size_asgi(scope)

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        start_time = time.perf_counter()

        if await self._try_handle_probe(scope, send, path, start_time):
            return

        if await self._try_handle_metrics(scope, send, path, start_time):
            return

        if await self._try_handle_fast_404(scope, send, path, start_time):
            return

        if await self._try_handle_rate_limiter(scope, send, start_time):
            return

        if await self._try_handle_static_or_media(scope, send, path, start_time):
            return

        async with self.async_backlog_tracker.track_request():
            await self._forward_to_django(scope, receive, send, method, path, start_time)

    async def _send_response(
        self,
        scope: Dict[str, Any],
        send: Callable,
        status_code: int,
        body: bytes,
        start_time: float,
        is_probe: bool = True,
    ):
        headers = [
            (b"content-type", b"text/plain"),
            (b"content-length", str(len(body)).encode("utf-8")),
            (b"cache-control", b"no-store, no-cache, must-revalidate, max-age=0"),
        ]
        await send({"type": ASGI_HTTP_RESPONSE_START, "status": status_code, "headers": headers})
        await send({"type": ASGI_HTTP_RESPONSE_BODY, "body": body})
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_asgi_request(
            scope,
            scope.get("method", "GET"),
            scope.get("path", ""),
            status_code,
            elapsed_ms,
            is_probe=is_probe,
        )

    def _log_asgi_request(
        self,
        scope: Dict[str, Any],
        method: str,
        path: str,
        status: int,
        elapsed_ms: float,
        is_probe: bool = False,
    ):
        if is_probe and not getattr(settings, "HURRICANE_LOG_PROBES", getattr(settings, "LOG_PROBES", False)):
            return

        if status < 400:
            log_method = access_log.info
        elif status < 500:
            log_method = access_log.warning
        else:
            log_method = access_log.error

        client = scope.get("client")
        remote_ip = client[0] if client else "127.0.0.1"

        if STRUCTLOG_ENABLED:
            bind_contextvars(
                hurricane=HURRICANE_DIST_VERSION,
                protocol="HTTP/1.1",
                method=method,
                path=path,
                status=status,
                request_time=elapsed_ms,
                remote_ip=remote_ip,
                id="n/a",
                traceparent="n/a",
            )
            log_method(f"TX {method} {path} {round(elapsed_ms, 2)}ms")
        else:
            log_method(f"{status} {method} {path} ({remote_ip}) {elapsed_ms:.2f}ms")


# Backward compatibility aliases
DjangoHandler = HurricaneWSGIGateway
HurricaneWSGIContainer = HurricaneWSGIGateway
