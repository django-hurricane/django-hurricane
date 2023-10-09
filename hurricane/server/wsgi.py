from types import TracebackType
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import tornado.wsgi
from tornado import escape, httputil
from tornado.ioloop import IOLoop


class HurricaneWSGIException(Exception):
    pass


class HurricaneWSGIContainer(tornado.wsgi.WSGIContainer):
    """
    Wrapper for the tornado WSGI Container, which creates a WSGI-compatible function runnable on Tornado's
    HTTP server. Additionally to tornado WSGI Container should be initialized with the specific handler.

    """

    def __init__(self, handler, wsgi_application, executor=None) -> None:
        self.handler = handler
        super(HurricaneWSGIContainer, self).__init__(
            wsgi_application, executor=executor
        )

    def _log(self, status_code: int, request: httputil.HTTPServerRequest) -> None:
        self.handler._status_code = status_code
        self.handler.application.log_request(self.handler)

    def __call__(self, request: httputil.HTTPServerRequest) -> None:
        IOLoop.current().spawn_callback(self.handle_request, request)

    async def handle_request(self, request: httputil.HTTPServerRequest) -> None:
        data: Dict[str, Any] = {}
        response: List[bytes] = []

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

        loop = IOLoop.current()
        app_response = await loop.run_in_executor(
            self.executor,
            self.wsgi_application,
            self.environ(request),
            start_response,
        )
        try:
            app_response_iter = iter(app_response)

            def next_chunk() -> Optional[bytes]:
                try:
                    return next(app_response_iter)
                except StopIteration:
                    # StopIteration is special and is not allowed to pass through
                    # coroutines normally.
                    return None

            while True:
                chunk = await loop.run_in_executor(self.executor, next_chunk)
                if chunk is None:
                    break
                response.append(chunk)
        finally:
            if hasattr(app_response, "close"):
                app_response.close()  # type: ignore
        body = b"".join(response)
        if not data:
            raise Exception("WSGI app did not call start_response")

        status_code_str, reason = data["status"].split(" ", 1)
        status_code = int(status_code_str)
        headers = data["headers"]  # type: List[Tuple[str, str]]
        header_set = set(k.lower() for (k, v) in headers)
        body = escape.utf8(body)
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
        assert request.connection is not None
        if request.method == "HEAD":
            request.connection.write_headers(start_line, header_obj)
        else:
            request.connection.write_headers(start_line, header_obj, chunk=body)
        request.connection.finish()
        self._log(status_code, request)
