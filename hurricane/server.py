import asyncio
import logging
from types import TracebackType
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import tornado
import tornado.web
import tornado.wsgi
from django.conf import settings
from django.core.management.base import SystemCheckError
from django.core.wsgi import get_wsgi_application
from django.db import OperationalError, connection
from tornado import escape, httputil

from hurricane.metrics.requests import RequestCounterMetric, RequestQueueLengthMetric, ResponseTimeAverageMetric

access_log = logging.getLogger("hurricane.server.access")
app_log = logging.getLogger("hurricane.server.application")
logger = logging.getLogger("hurricane.server.general")
metrics_log = logging.getLogger("hurricane.server.metrics")


class HurricaneWSGIContainer(tornado.wsgi.WSGIContainer):
    def __init__(self, handler, wsgi_application) -> None:
        self.handler = handler
        super(HurricaneWSGIContainer, self).__init__(wsgi_application)

    def _log(self, status_code: int, request: httputil.HTTPServerRequest) -> None:
        self.handler._status_code = status_code

    def __call__(self, request: httputil.HTTPServerRequest) -> None:
        data = {}  # type: Dict[str, Any]
        response = []  # type: List[bytes]

        def start_response(
            status: str,
            headers: List[Tuple[str, str]],
            exc_info: Optional[
                Tuple[
                    "Optional[Type[BaseException]]",
                    Optional[BaseException],
                    Optional[TracebackType],
                ]
            ] = None,
        ) -> Callable[[bytes], Any]:
            data["status"] = status
            data["headers"] = headers
            return response.append

        app_response = self.wsgi_application(self.environ(request), start_response)
        try:
            response.extend(app_response)
            body = b"".join(response)
        finally:
            if hasattr(app_response, "close"):
                app_response.close()  # type: ignore
        if not data:
            raise Exception("WSGI app did not call start_response")

        status_code_str, reason = data["status"].split(" ", 1)
        status_code = int(status_code_str)
        headers = data["headers"]  # type: List[Tuple[str, str]]
        header_set = set(k.lower() for (k, v) in headers)
        # handle WSGI's protocol assumption the web server to strip content from HEAD requests
        # and leave content length header as is.
        # - from Django documentation:
        # Web servers should automatically strip the content of responses to HEAD requests while leaving the headers
        # unchanged, so you may handle HEAD requests exactly like GET requests in your views. Since some software,
        # such as link checkers, rely on HEAD requests, you might prefer using require_safe instead of require_GET.
        if request.method != "HEAD":
            body = escape.utf8(body)
        else:
            body = ""
        if status_code != 304:
            if "content-length" not in header_set:
                headers.append(("Content-Length", str(len(body))))
            if "content-type" not in header_set:
                headers.append(("Content-Type", "text/html; charset=UTF-8"))
        if "server" not in header_set:
            headers.append(("Server", "TornadoServer/%s" % tornado.version))

        start_line = httputil.ResponseStartLine("HTTP/1.1", status_code, reason)
        header_obj = httputil.HTTPHeaders()
        for key, value in headers:
            header_obj.add(key, value)
        if request.connection is None:
            raise ValueError("No connection")
        request.connection.write_headers(start_line, header_obj, chunk=body)
        request.connection.finish()
        self._log(status_code, request)


class DjangoHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.django = HurricaneWSGIContainer(self, get_wsgi_application())

    def prepare(self) -> None:
        self.django(self.request)
        self._finished = True
        self._log()
        self.on_finish()


class HurricaneApplication(tornado.web.Application):
    def __init__(self, *args, **kwargs):
        self.collect_metrics = True
        if "metrics" in kwargs:
            self.collect_metrics = kwargs["metrics"]
        super(HurricaneApplication, self).__init__(*args, **kwargs)

    def log_request(self, handler: DjangoHandler) -> None:
        """Writes a completed HTTP request to the logs. """
        if handler.get_status() < 400:
            log_method = access_log.info
        elif handler.get_status() < 500:
            log_method = access_log.warning
        else:
            log_method = access_log.error
        request_time = 1000.0 * handler.request.request_time()
        log_method(
            "%d %s %.2fms",
            handler.get_status(),
            handler._request_summary(),
            request_time,
        )
        if self.collect_metrics:
            RequestCounterMetric.increment()
            ResponseTimeAverageMetric.add_value(request_time)


class DjangoCheckHandler(tornado.web.RequestHandler):
    """
    This handler runs with ever call to the probe endpoint which is supposed to be used
    with Kubernetes 'Liveness Probes'. The DjangoCheckHandler calls Django's Check Framework which
    can be used to determine the application's health state during its operation.
    """

    def initialize(self, check_handler):
        self.check = check_handler

    def compute_etag(self):
        return None

    def _check(self):
        try:
            self.check()
            if settings.DATABASES:
                # once a connection has been established, this will be successful
                # (even if the connection is gone later on)
                connection.ensure_connection()
        except SystemCheckError as e:
            if settings.DEBUG:
                self.write("django check error: " + str(e))
            else:
                self.write("check error")
            self.set_status(500)
        except OperationalError as e:
            if settings.DEBUG:
                self.write("django database error: " + str(e))
            else:
                self.write("db error")
            self.set_status(500)
        else:
            if response_average_time := ResponseTimeAverageMetric.get():
                self.write(
                    f"Average response time: {response_average_time:.2f}ms Request "
                    f"queue size: {RequestQueueLengthMetric.get()} Rx"
                )
            else:
                self.write("alive")

    def set_extra_headers(self, path):
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")

    def get(self):
        self._check()

    def post(self):
        self._check()


def make_probe_server(options, check_func):
    """ create probe route application """
    handlers = [(options["probe"], DjangoCheckHandler, {"check_handler": check_func})]
    return HurricaneApplication(handlers, debug=options["debug"], metrics=False)


def make_http_server(options, check_func, include_probe=False):
    """ create all routes for this application """
    if include_probe:
        handlers = [(options["probe"], DjangoCheckHandler, {"check_handler": check_func})]
    else:
        handlers = []
    # if static file serving is enabled
    if options["static"]:
        logger.info(f"Serving static files under {settings.STATIC_URL} from {settings.STATIC_ROOT}")
        handlers.append(
            (
                f"{settings.STATIC_URL}(.*)",
                tornado.web.StaticFileHandler,
                {"path": settings.STATIC_ROOT},
            )
        )
    # if media file serving is enabled
    if options["media"]:
        logger.info(f"Serving media files under {settings.MEDIA_URL} from {settings.MEDIA_ROOT}")
        handlers.append(
            (
                f"{settings.MEDIA_URL}(.*)",
                tornado.web.StaticFileHandler,
                {"path": settings.MEDIA_ROOT},
            )
        )

    # append the django routing system
    handlers.append((".*", DjangoHandler))
    return HurricaneApplication(handlers, debug=options["debug"], metrics=not options["no_metrics"])
