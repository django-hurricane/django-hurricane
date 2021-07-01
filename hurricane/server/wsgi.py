from types import TracebackType
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import tornado.wsgi
from asgiref.sync import sync_to_async
from tornado import escape, httputil


class HurricaneWSGIException(Exception):
    pass


class HurricaneWSGIContainer(tornado.wsgi.WSGIContainer):
    """
    Wrapper for the tornado WSGI Container, which creates a WSGI-compatible function runnable on Tornado's
    HTTP server. Additionally to tornado WSGI Container should be initialized with the specific handler.

    """

    def __init__(self, handler, wsgi_application) -> None:
        self.handler = handler
        super(HurricaneWSGIContainer, self).__init__(wsgi_application)

    def _log(self, status_code: int, request: httputil.HTTPServerRequest) -> None:
        self.handler._status_code = status_code

    async def __call__(self, request: httputil.HTTPServerRequest) -> None:
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

        sync_wsgi_data = sync_to_async(self.wsgi_application)
        app_response = await sync_wsgi_data(self.environ(request), start_response)

        try:
            response.extend(app_response)
            body = b"".join(response)
        finally:
            if hasattr(app_response, "close"):
                app_response.close()  # type: ignore
        if not data:
            raise HurricaneWSGIException("WSGI app did not call start_response")

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
