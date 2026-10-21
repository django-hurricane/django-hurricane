import mimetypes
import multiprocessing
import os
import re
import threading
import time
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from django.conf import settings
from django.core.management.base import SystemCheckError
from django.core.wsgi import get_wsgi_application
from django.db import OperationalError, connection
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


class HurricaneWSGIGateway:
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
        self.options = options or {}
        self.django_app = django_app or get_wsgi_application()
        self.check_func = check_func
        self.include_probe = include_probe

        # Concurrency & backlog tracking
        threads = self.options.get("workers") or min(32, (os.cpu_count() or 1) + 4)
        self.backlog_tracker = WorkerBacklogTracker(max_threads=threads)
        self.req_queue_len = self.options.get("req_queue_len", 10)
        self.max_lifetime = self.options.get("max_lifetime")
        self.collect_metrics = not self.options.get("no_metrics", False)

        # Paths
        self.liveness_path = self._normalize_path(self.options.get("liveness_probe", "/alive"))
        self.readiness_path = self._normalize_path(self.options.get("readiness_probe", "/ready"))
        self.startup_path = self._normalize_path(self.options.get("startup_probe", "/startup"))
        self.metrics_path = self._normalize_path(self.options.get("metrics_path", "/metrics"))

        self.webhook_url = self.options.get("webhook_url")
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

    def __call__(self, environ: Dict[str, Any], start_response: Callable) -> Any:
        path = environ.get("PATH_INFO", "")
        method = environ.get("REQUEST_METHOD", "GET")
        start_time = time.perf_counter()

        # Handle Probes and Metrics if enabled on this gateway
        if self.include_probe and not self.options.get("no_probe", False):
            if self._matches_path(path, self.liveness_path):
                return self._handle_liveness(environ, start_response, start_time)
            if self._matches_path(path, self.readiness_path):
                return self._handle_readiness(environ, start_response, start_time)
            if self._matches_path(path, self.startup_path):
                return self._handle_startup(environ, start_response, start_time)

        if self.collect_metrics and self._matches_path(path, self.metrics_path):
            return self._handle_metrics(environ, start_response, start_time)

        # Handle Static & Media
        if self.static_enabled and path.startswith(self.static_url):
            return self._handle_static_file(
                environ, start_response, path, self.static_url, self.static_root, start_time
            )
        if self.media_enabled and path.startswith(self.media_url):
            return self._handle_static_file(environ, start_response, path, self.media_url, self.media_root, start_time)

        # Early Fast-404 protection (block attack signatures and invalid prefixes before Django)
        if self.fast_404:
            drop_info = self.fast_404.should_drop(path)
            if drop_info:
                reason_type, detail = drop_info
                self.fast_404.log_drop(environ, path, reason_type, detail)
                status, headers, body = self.fast_404.get_response()
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                self._log_request(environ, method, path, 404, elapsed_ms, is_probe=False)
                if self.collect_metrics:
                    RequestCounterMetric.increment()
                    ResponseTimeAverageMetric.add_value(elapsed_ms)
                start_response(status, headers)
                return [body]

        # Check max_body_size
        max_body_size = self.options.get("max_body_size")
        if max_body_size:
            try:
                content_length = int(environ.get("CONTENT_LENGTH") or 0)
                if content_length > max_body_size:
                    raise ConnectionResetError("Request body size exceeded max_body_size")
            except (ValueError, TypeError):
                pass

        # Forward standard traffic to Django with backlog tracking & logging
        status_container: List[str] = ["200 OK"]
        headers_container: List[List[Tuple[str, str]]] = [[]]

        def custom_start_response(status: str, headers: List[Tuple[str, str]], exc_info=None):
            status_container[0] = status
            headers_container[0] = headers
            return start_response(status, headers, exc_info)

        with self.backlog_tracker.track_request():
            response_iter = self.django_app(environ, custom_start_response)

        # Extract HTTP status code for logging
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

    def _handle_liveness(self, environ: Dict[str, Any], start_response: Callable, start_time: float) -> List[bytes]:
        # Check if startup is finished
        if not StartupTimeMetric.get():
            return self._send_probe_response(environ, start_response, 400, b"Startup is not finished yet", start_time)

        # Max lifetime check
        if self.max_lifetime and RequestCounterMetric.get() > self.max_lifetime:
            return self._send_probe_response(environ, start_response, 400, b"Max lifetime reached", start_time)

        # Run system check & db connection check
        status, body = self._run_custom_check("liveness", HealthMetric)
        if status == 200 and body == b"OK":
            if resp_avg := ResponseTimeAverageMetric.get():
                body = (
                    f"Average response time: {resp_avg:.2f}ms Request queue size: {RequestQueueLengthMetric.get()} Rx"
                ).encode("utf-8")
            else:
                body = b"alive"

        return self._send_probe_response(environ, start_response, status, body, start_time)

    def _handle_readiness(self, environ: Dict[str, Any], start_response: Callable, start_time: float) -> List[bytes]:
        # Check if startup is finished
        if not StartupTimeMetric.get():
            return self._send_probe_response(environ, start_response, 400, b"Startup is not finished yet", start_time)

        # Check backlog limit
        current_backlog = RequestQueueLengthMetric.get()
        if current_backlog >= self.req_queue_len:
            self._update_webhook_and_metric(ReadinessMetric, status_succeeded=False)
            return self._send_probe_response(environ, start_response, 400, b"Request queue limit exceeded", start_time)

        # Run system check & db check
        status, body = self._run_custom_check("readiness", ReadinessMetric)
        return self._send_probe_response(environ, start_response, status, body, start_time)

    def _handle_startup(self, environ: Dict[str, Any], start_response: Callable, start_time: float) -> List[bytes]:
        startup_time = StartupTimeMetric.get()
        if startup_time:
            body = f"Startup was finished {startup_time}".encode("utf-8")
            return self._send_probe_response(environ, start_response, 200, body, start_time)
        return self._send_probe_response(environ, start_response, 400, b"Startup is not finished yet", start_time)

    def _handle_metrics(self, environ: Dict[str, Any], start_response: Callable, start_time: float) -> List[bytes]:
        from hurricane.metrics.shared import SharedMetrics

        # Sync standard Prometheus metric objects from shared storage
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

        # Refresh any dynamic CalculatedMetrics
        for _, metric in registry.metrics.items():
            try:
                metric.get()
            except Exception:
                pass

        payload = generate_latest()
        headers = [
            ("Content-Type", CONTENT_TYPE_LATEST),
            ("Content-Length", str(len(payload))),
            ("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"),
        ]
        start_response("200 OK", headers)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_request(
            environ,
            environ.get("REQUEST_METHOD", "GET"),
            environ.get("PATH_INFO", "/metrics"),
            200,
            elapsed_ms,
            is_probe=True,
        )
        return [payload]

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
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self._log_request(environ, "GET", request_path, 404, elapsed_ms, is_probe=False)
            return [b"Not Found"]

        content_type, _ = mimetypes.guess_type(file_path)
        content_type = content_type or "application/octet-stream"
        file_size = os.path.getsize(file_path)

        headers = [
            ("Content-Type", content_type),
            ("Content-Length", str(file_size)),
        ]
        start_response("200 OK", headers)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_request(environ, "GET", request_path, 200, elapsed_ms, is_probe=False)

        with open(file_path, "rb") as f:
            return [f.read()]

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

    def _log_request(
        self,
        environ: Dict[str, Any],
        method: str,
        path: str,
        status: int,
        elapsed_ms: float,
        is_probe: bool = False,
    ):
        if is_probe and not getattr(settings, "LOG_PROBES", False):
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


class HurricaneASGIGateway:
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
        from django.core.asgi import get_asgi_application

        self.options = options or {}
        self.django_app = django_app or get_asgi_application()
        self.check_func = check_func
        self.include_probe = include_probe

        # Backlog & concurrency tracking
        threads = self.options.get("workers") or min(32, (os.cpu_count() or 1) + 4)
        self.backlog_tracker = WorkerBacklogTracker(max_threads=threads)
        self.req_queue_len = self.options.get("req_queue_len", 10)
        self.max_lifetime = self.options.get("max_lifetime")
        self.collect_metrics = not self.options.get("no_metrics", False)

        # Paths
        self.liveness_path = self._normalize_path(self.options.get("liveness_probe", "/alive"))
        self.readiness_path = self._normalize_path(self.options.get("readiness_probe", "/ready"))
        self.startup_path = self._normalize_path(self.options.get("startup_probe", "/startup"))
        self.metrics_path = self._normalize_path(self.options.get("metrics_path", "/metrics"))
        self.webhook_url = self.options.get("webhook_url")

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

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.django_app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        start_time = time.perf_counter()

        # Handle Probes and Metrics
        if self.include_probe and not self.options.get("no_probe", False):
            if self._matches_path(path, self.liveness_path):
                await self._handle_liveness(scope, receive, send, start_time)
                return
            if self._matches_path(path, self.readiness_path):
                await self._handle_readiness(scope, receive, send, start_time)
                return
            if self._matches_path(path, self.startup_path):
                await self._handle_startup(scope, receive, send, start_time)
                return

        if self.collect_metrics and self._matches_path(path, self.metrics_path):
            await self._handle_metrics(scope, receive, send, start_time)
            return

        # Forward standard traffic to Django
        status_code_container = [200]

        async def logging_send(message: Mapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status_code_container[0] = int(message.get("status", 200))
            await send(message)

        with self.backlog_tracker.track_request():
            await self.django_app(scope, receive, logging_send)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_asgi_request(scope, method, path, status_code_container[0], elapsed_ms, is_probe=False)

        if self.collect_metrics:
            RequestCounterMetric.increment()
            ResponseTimeAverageMetric.add_value(elapsed_ms)

    async def _handle_liveness(self, scope, receive, send, start_time: float):
        if not StartupTimeMetric.get():
            await self._send_response(scope, send, 400, b"Startup is not finished yet", start_time)
            return

        if self.max_lifetime and RequestCounterMetric.get() > self.max_lifetime:
            await self._send_response(scope, send, 400, b"Max lifetime reached", start_time)
            return

        status, body = self._run_custom_check("liveness", HealthMetric)
        if status == 200 and body == b"OK":
            if resp_avg := ResponseTimeAverageMetric.get():
                body = (
                    f"Average response time: {resp_avg:.2f}ms Request queue size: {RequestQueueLengthMetric.get()} Rx"
                ).encode("utf-8")
            else:
                body = b"alive"

        await self._send_response(scope, send, status, body, start_time)

    async def _handle_readiness(self, scope, receive, send, start_time: float):
        if not StartupTimeMetric.get():
            await self._send_response(scope, send, 400, b"Startup is not finished yet", start_time)
            return

        current_backlog = self.backlog_tracker.current_backlog
        RequestQueueLengthMetric.set(current_backlog)

        if current_backlog >= self.req_queue_len:
            self._update_webhook_and_metric(ReadinessMetric, status_succeeded=False)
            await self._send_response(scope, send, 400, b"Request queue limit exceeded", start_time)
            return

        status, body = self._run_custom_check("readiness", ReadinessMetric)
        await self._send_response(scope, send, status, body, start_time)

    async def _handle_startup(self, scope, receive, send, start_time: float):
        startup_time = StartupTimeMetric.get()
        if startup_time:
            body = f"Startup was finished {startup_time}".encode("utf-8")
            await self._send_response(scope, send, 200, body, start_time)
            return
        await self._send_response(scope, send, 400, b"Startup is not finished yet", start_time)

    async def _handle_metrics(self, scope, receive, send, start_time: float):
        from hurricane.metrics.shared import SharedMetrics

        # Sync standard Prometheus metric objects from shared storage
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
                if getattr(metric, "is_async", False):
                    await metric.get()
                else:
                    metric.get()
            except Exception:
                pass

        payload = generate_latest()
        headers = [
            (b"content-type", CONTENT_TYPE_LATEST.encode("utf-8")),
            (b"content-length", str(len(payload)).encode("utf-8")),
            (b"cache-control", b"no-store, no-cache, must-revalidate, max-age=0"),
        ]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": payload})

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_asgi_request(scope, "GET", scope.get("path", "/metrics"), 200, elapsed_ms, is_probe=True)

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

    async def _send_response(self, scope, send, status_code: int, body: bytes, start_time: float):
        headers = [
            (b"content-type", b"text/plain"),
            (b"content-length", str(len(body)).encode("utf-8")),
            (b"cache-control", b"no-store, no-cache, must-revalidate, max-age=0"),
        ]
        await send({"type": "http.response.start", "status": status_code, "headers": headers})
        await send({"type": "http.response.body", "body": body})
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._log_asgi_request(
            scope,
            scope.get("method", "GET"),
            scope.get("path", ""),
            status_code,
            elapsed_ms,
            is_probe=True,
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
        if is_probe and not getattr(settings, "LOG_PROBES", False):
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
