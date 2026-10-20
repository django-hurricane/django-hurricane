import http.client
import http.server
import json
import mimetypes
import os
import time


class HTTPClient(object):
    class Response(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.__dict__ = self

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.conn = http.client.HTTPConnection(host=host, port=port)

    def get(self, path: str) -> Response:
        for _ in range(10):
            try:
                self.conn.request("GET", path)
                res = self.conn.getresponse()
                data = res.read()
                return self.Response({"status": res.status, "text": data.decode("utf-8")})
            except (ConnectionRefusedError, http.client.CannotSendRequest, http.client.ResponseNotReady):
                time.sleep(0.1)
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = http.client.HTTPConnection(self.host, self.port)
        self.conn.request("GET", path)
        res = self.conn.getresponse()
        data = res.read()
        return self.Response({"status": res.status, "text": data.decode("utf-8")})

    def head(self, path: str) -> Response:
        self.conn.request("HEAD", path)
        res = self.conn.getresponse()
        data = res.read()
        return self.Response({"status": res.status, "text": data.decode("utf-8")})

    def post(self, path: str, data: dict) -> Response:
        self.conn.request("POST", path, json.dumps(data).encode())
        res = self.conn.getresponse()
        datas = res.read()  # type: bytes
        return self.Response({"status": res.status, "text": datas.decode("utf-8")})

    def post_file(self, path: str, file_path: str) -> Response:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        filename = os.path.basename(file_path)
        content_type, _ = mimetypes.guess_type(file_path)

        with open(file_path, "rb") as f:
            file_content = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
            f"{file_content.decode('latin1')}\r\n"
            f"--{boundary}--\r\n"
        )

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        }

        self.conn.request("POST", path, body.encode("latin1"), headers)
        res = self.conn.getresponse()
        if res.status in (413, 500):
            raise ConnectionResetError("Connection reset due to body size limit exceeded")
        data = res.read()

        return self.Response({"status": res.status, "text": data.decode("utf-8")})


class LoggingServer:
    try:
        import structlog

        logger = structlog.get_logger(__name__)
    except ImportError:
        import logging

        logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)


class WebhookTestHandler(http.server.BaseHTTPRequestHandler, LoggingServer):
    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8"))
            self.logger.info(data.get("status", "No status received"))
            self.logger.info(data.get("traceback", "No traceback received"))
        except Exception:
            pass
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Received webhook")

    def log_message(self, format, *args):
        pass


class WebhookHTTPServer(http.server.HTTPServer):
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(http.server.socket.SOL_SOCKET, http.server.socket.SO_REUSEADDR, 1)
        try:
            self.socket.setsockopt(http.server.socket.SOL_SOCKET, http.server.socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        super().server_bind()


class WebhookReceiverServer(LoggingServer):
    def make_http_receiver_server(self, port: int = 8074):
        return WebhookHTTPServer(("0.0.0.0", port), WebhookTestHandler)

    def make_http_receiver_app(self):
        return self.make_http_receiver_server()
