import http
import json
import mimetypes
import os

import pika
import tornado.ioloop
import tornado.web


class HTTPClient(object):
    class Response(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.__dict__ = self

    def __init__(self, host: str, port: int):
        self.conn = http.client.HTTPConnection(host=host, port=port)

    def get(self, path: str) -> Response:
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
            f'{file_content.decode("latin1")}\r\n'
            f"--{boundary}--\r\n"
        )

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        }

        self.conn.request("POST", path, body.encode("latin1"), headers)
        res = self.conn.getresponse()
        data = res.read()

        return self.Response({"status": res.status, "text": data.decode("utf-8")})


class TestPublisher(object):
    def __init__(self, host, port, vhost="/"):
        parameters = pika.ConnectionParameters(host=host, port=port, virtual_host=vhost)
        connection = pika.BlockingConnection(parameters)
        self.channel = connection.channel()

    def publish(self, exchange: str, queue: str, message: str) -> None:
        self.channel.basic_publish(exchange=exchange, routing_key=queue, body=message)


class LoggingServer:
    try:
        import structlog

        logger = structlog.get_logger(__name__)
    except ImportError:
        import logging

        logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)


class WebhookTestHandler(tornado.web.RequestHandler, LoggingServer):
    def post(self):
        data = json.loads(self.request.body.decode("utf-8"))
        self.logger.info(data.get("status", "No status received"))
        self.logger.info(data.get("traceback", "No traceback received"))
        self.write("Received webhook")


class WebhookReceiverServer(LoggingServer):
    def make_http_receiver_app(self):
        return tornado.web.Application([("/webhook", WebhookTestHandler)])
