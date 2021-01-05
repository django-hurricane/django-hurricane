import http
import json

import pika


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
        data = res.read()
        return self.Response({"status": res.status, "text": data.decode("utf-8")})


class TestPublisher(object):
    def __init__(self, host, port, vhost="/"):
        parameters = pika.ConnectionParameters(host=host, port=port, virtual_host=vhost)
        connection = pika.BlockingConnection(parameters)
        self.channel = connection.channel()

    def publish(self, exchange: str, queue: str, message: str) -> None:
        self.channel.basic_publish(exchange=exchange, routing_key=queue, body=message)
