import http
import json
import subprocess
from queue import Empty, Queue
from threading import Thread
from time import sleep
from typing import Tuple

from django.test import SimpleTestCase


class HurricaneServerDriver(object):
    def get_server_host_port(self, probe_port=False) -> Tuple[str, int]:
        if probe_port:
            port = self.probe_port
        else:
            port = self.port
        if self.proc:
            return "localhost", port
        else:
            return None, None

    def start_server(self, params=None, coverage=True) -> None:
        def enqueue_output(proc, queue):
            out = proc.stdout
            for line in iter(out.readline, b""):
                queue.put(line.decode("utf-8"))
            out.close()

        if coverage:
            base_command = [
                "coverage",
                "run",
                "--source=hurricane/",
                "manage.py",
                "serve",
            ]
        else:
            base_command = ["python", "manage.py", "serve"]
        if params:
            base_command = base_command + params
        if params and "--port" in params:
            self.port = int(params[params.index("--port") + 1])
        else:
            self.port = 8000

        if params and "--probe-port" in params:
            self.probe_port = int(params[params.index("--probe-port") + 1])
        else:
            self.probe_port = 8001

        self.proc = subprocess.Popen(base_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.q = Queue()
        self.t = Thread(target=enqueue_output, args=(self.proc, self.q))
        self.t.daemon = True
        self.t.start()
        # pause one sec to start the server as background process
        sleep(1)

    def stop_server(self) -> None:
        if self.proc:
            self.proc.terminate()

    def get_server_output(self, read_all=False) -> Tuple[str, str]:
        if self.proc:
            if read_all:
                lines = []
                while True:
                    try:
                        line = self.q.get(timeout=0.5)
                        lines.append(line)
                    except Empty:
                        break
                return "".join(lines), ""
            else:
                try:
                    line = self.q.get(timeout=1)
                    if line:
                        return line, ""
                except Empty:
                    pass
                return "", ""
        return "", ""


class HurricanServerTest(SimpleTestCase):
    class Client(object):
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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = HurricaneServerDriver()

    @property
    def app_client(self):
        host, port = self.server.get_server_host_port()
        return self.Client(host, port)

    @property
    def probe_client(self):
        host, port = self.server.get_server_host_port(probe_port=True)
        return self.Client(host, port)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop_server()
        super().tearDownClass()

    @staticmethod
    def cylce_server(*args, **kwargs):
        def _cycle_server(function):
            def wrapper(self):
                if "args" in kwargs:
                    _args = kwargs["args"]
                else:
                    _args = None
                # run this hurricane server with coverage
                # default is True
                if "coverage" in kwargs:
                    coverage = kwargs["coverage"]
                else:
                    coverage = True
                self.server.start_server(_args, coverage)
                try:
                    function(self)
                except Exception as e:
                    self.server.stop_server()
                    raise e
                else:
                    self.server.stop_server()

            return wrapper

        if len(args) == 1 and callable(args[0]):
            return _cycle_server(args[0])
        else:
            return _cycle_server
