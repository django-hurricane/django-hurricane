import os
import signal
import socket
import subprocess
from queue import Empty, Queue
from threading import Thread
from time import sleep
from typing import Dict, List, Optional, Tuple, Union

MANAGE_FILE = "manage.py"


class BusyPortException(Exception):
    pass


class HurricaneBaseDriver(object):
    proc = None
    log_lines: List[str] = []
    base_command: List[str] = []
    coverage_base_command: List[str] = []
    test_string = ""
    ports = [8000, 8001]
    port = 8000
    probe_port = 8001
    source = "--source=hurricane/"
    _env: Optional[Dict] = {}

    def _free_ports(self):
        try:
            import psutil

            for conn in psutil.net_connections(kind="tcp"):
                if conn.laddr and conn.laddr.port in self.ports and conn.pid:
                    try:
                        p = psutil.Process(conn.pid)
                        p.kill()
                        p.wait(timeout=1)
                    except Exception:
                        pass
        except Exception:
            pass

    def __init__(self):
        for port in self.ports:
            for _ in range(30):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        try:
                            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                        except (AttributeError, OSError):
                            pass
                        sock.bind(("127.0.0.1", port))
                        break
                except OSError:
                    self._free_ports()
                    sleep(0.1)
            else:
                raise BusyPortException(f"Port {port} already in use.")

    def get_server_host_port(self, probe_port=False) -> Union[Tuple[str, int], Tuple[None, None]]:
        port = self.probe_port if probe_port else self.port
        if self.proc:
            return "localhost", port
        else:
            return None, None

    def get_output(self, read_all=False) -> Optional[Tuple[str, str]]:
        if read_all:
            while True:
                try:
                    line = self.q.get(timeout=0.5)
                    self.log_lines.append(line)
                except Empty:
                    break
            return "".join(self.log_lines), ""
        else:
            try:
                line = self.q.get(timeout=1)
                if line:
                    return line, ""
                return "", ""
            except Empty:
                return None

    def _get_env(self):
        return os.environ.copy()

    def _start(self, params: Optional[List[str]] = None, coverage: bool = True) -> None:
        self.log_lines = []
        base_command = self.coverage_base_command if coverage else self.base_command

        def enqueue_stdout(proc, queue):
            out = proc.stdout
            for line in iter(out.readline, b""):
                queue.put(line.decode("utf-8"))
            out.close()

        def enqueue_stderr(proc, queue):
            out = proc.stderr
            for line in iter(out.readline, b""):
                queue.put(line.decode("utf-8"))
            out.close()

        params = params if params else []

        base_command = base_command + params
        self.set_ports(params, self._env)

        self.proc = subprocess.Popen(  # type: ignore
            base_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._get_env(),
            preexec_fn=os.setsid,
        )
        self.pgid = self.proc.pid
        self.q = Queue()  # type: Queue
        self.t_stderr = Thread(target=enqueue_stderr, args=(self.proc, self.q))
        self.t_stdout = Thread(target=enqueue_stdout, args=(self.proc, self.q))
        self.t_stderr.daemon = True
        self.t_stderr.start()
        self.t_stdout.daemon = True
        self.t_stdout.start()
        # wait a maximum of 5 seconds for server startup to complete
        for _ in range(50):
            if self.proc:
                out, _ = self.get_output(read_all=True)  # type: ignore
            else:
                out = ""
            if (
                "Starting HTTP Server on port" in out
                or "HTTP configured" in out
                or (self.test_string and self.test_string in out)
            ):
                break
            sleep(0.1)

    def _stop(self):
        pgid = getattr(self, "pgid", None)
        if pgid:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except Exception:
                pass
            if self.proc:
                try:
                    self.proc.wait(timeout=1.0)
                except Exception:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except Exception:
                        pass
            self.pgid = None

        if self.proc:
            try:
                self.proc.kill()
                self.proc.wait(timeout=2)
            except Exception:
                pass
            self.proc = None
        self._free_ports()
        sleep(0.1)

    def set_ports(self, params, env: Optional[Dict] = None) -> None:
        env = env or {}
        if "--port" in params:
            self.port = int(params[params.index("--port") + 1])
        elif "HURRICANE_PORT" in env:
            self.port = int(env["HURRICANE_PORT"])
        else:
            self.port = 8000

        if "--probe-port" in params:
            self.probe_port = int(params[params.index("--probe-port") + 1])
        elif "HURRICANE_PROBE_PORT" in env:
            self.probe_port = int(env["HURRICANE_PROBE_PORT"])
        else:
            self.probe_port = self.port + 1 if self.port != 8000 else 8001

        self.ports = list({self.port, self.probe_port, 8000, 8001})


class HurricaneServerDriver(HurricaneBaseDriver):
    coverage_base_command = [
        "coverage",
        "run",
        HurricaneBaseDriver.source,
        MANAGE_FILE,
        "serve",
    ]
    base_command = ["python", MANAGE_FILE, "serve"]
    test_string = "Starting HTTP Server on port"
    _env: Dict = {}

    def _get_env(self):
        env = super(HurricaneServerDriver, self)._get_env()
        env.update(self._env)
        return env

    def start_server(
        self,
        params: Optional[List[str]] = None,
        coverage: bool = True,
        env: Optional[Dict] = None,
    ) -> None:
        self._env = env or dict()
        self._start(params, coverage)

    def stop_server(self) -> None:
        self._stop()


class HurricaneWebhookServerDriver(HurricaneBaseDriver):
    ports = [8074]
    coverage_base_command = [
        "coverage",
        "run",
        "-m",
        HurricaneBaseDriver.source,
        "hurricane.testing.start_webhook_receiver",
    ]
    base_command = ["python", "-m", "hurricane.testing.start_webhook_receiver"]
    test_string = "Started webhook receiver server"
    _env: Optional[Dict] = {}

    def _get_env(self):
        env = super(HurricaneWebhookServerDriver, self)._get_env()
        env.update(self._env)
        return env

    def start_server(
        self,
        params: Optional[List[str]] = None,
        coverage: bool = True,
        env: Optional[Dict] = None,
    ) -> None:
        self._env = env or dict()
        self._start(params, coverage)

    def stop_server(self) -> None:
        self._stop()
