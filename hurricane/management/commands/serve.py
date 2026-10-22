import asyncio
import functools
import os
import signal
import sys
import threading
import time
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from granian import Granian
from granian.constants import Interfaces

from hurricane.management.commands import HURRICANE_DIST_VERSION
from hurricane.metrics.shared import cleanup_shm
from hurricane.server import (
    HTTP_CONFIGURED_EVENT,
    PROBE_CONFIGURED_EVENT,
    PROMETHEUS_CONFIGURED_EVENT,
    check_db_and_migrations,
    check_mem_allocations,
    command_task,
    logger,
    make_http_server_and_listen,
    make_probe_server,
    sanitize_probes,
    static_watch,
)
from hurricane.server.debugging import setup_debugging
from hurricane.server.granian import configure_granian
from hurricane.server.loggers import STRUCTLOG_ENABLED


def _get_setting_value(descriptor: str) -> Any:
    """Retrieve option value from Django settings, checking prefixed then unprefixed name."""
    if hasattr(settings, descriptor):
        return getattr(settings, descriptor)
    unprefixed = descriptor.removeprefix("HURRICANE_")
    if hasattr(settings, unprefixed):
        return getattr(settings, unprefixed)
    raise AttributeError(f"Setting {descriptor} not found")


def _get_env_value(descriptor: str) -> Optional[Any]:
    """Retrieve option value from environment variables, checking prefixed then unprefixed name."""
    val = os.environ.get(descriptor)
    if val is None:
        val = os.environ.get(descriptor.removeprefix("HURRICANE_"))
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return val


class Command(BaseCommand):
    """
    Start a Granian-powered Django web server by using ``python manage.py serve <arguments>``.

    It can run Django management commands with the ``--command`` flag, that will be executed asynchronously.
    The application server will only be started upon successful execution of management commands. During execution
    of management commands the startup probe responds with a status 400.
    """

    help = "Start a Granian-powered Django web server"

    def add_arguments(self, parser):
        parser.add_argument("--static", action="store_true", help="Serve collected static files")
        parser.add_argument("--media", action="store_true", help="Serve media files")
        parser.add_argument("--autoreload", action="store_true", help="Reload code on change")
        parser.add_argument("--debug", action="store_true", help="Set Debug flag")
        parser.add_argument("--port", type=int, default=8000, help="The port for the server to listen on")
        parser.add_argument(
            "--metrics",
            type=str,
            dest="metrics_path",
            default="/metrics",
            help="The exposed path (default is /metrics) to export Prometheus metrics",
        )
        parser.add_argument(
            "--liveness-probe",
            type=str,
            default="/alive",
            help="The exposed path (default is /alive) for probes to check liveness",
        )
        parser.add_argument(
            "--readiness-probe",
            type=str,
            default="/ready",
            help="The exposed path (default is /ready) for probes to check readiness",
        )
        parser.add_argument(
            "--startup-probe",
            type=str,
            default="/startup",
            help="The exposed path (default is /startup) for probes to check startup",
        )
        parser.add_argument(
            "--probe-port",
            type=int,
            help="The port for the probe route to listen on",
        )
        parser.add_argument("--req-queue-len", type=int, default=None, help="Length of the request queue (WSGI only)")
        parser.add_argument("--no-probe", action="store_true", help="Disable probe endpoint")
        parser.add_argument("--no-metrics", action="store_true", help="Disable metrics collection")
        parser.add_argument("--command", type=str, action="append", nargs="+")
        parser.add_argument(
            "--check-migrations",
            action="store_true",
            help="Check if migrations were applied",
        )
        parser.add_argument(
            "--check-migrations-apply",
            action="store_true",
            help="Check if migrations were applied and apply them if needed",
        )
        parser.add_argument(
            "--debugger",
            action="store_true",
            help="Open a debugger port according to the Debug Adapter Protocol",
        )
        parser.add_argument(
            "--debugger-port",
            type=int,
            default=5678,
            help="The port for the debug client to attach",
        )
        parser.add_argument(
            "--webhook-url",
            type=str,
            help="Url for webhooks",
        )
        parser.add_argument(
            "--max-lifetime",
            type=int,
            default=None,
            help="Maximum requests after which pod is restarted (default = None)",
        )
        parser.add_argument(
            "--max-memory",
            type=int,
            default=None,
            help="Maximum memory (Resident Set Size) in Mb before process reloads (default = None, no reload)",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=None,
            help="Number of thread workers to be used for the server (default = Number of CPUs + 4)",
        )
        parser.add_argument(
            "--static-watch",
            type=str,
            action="append",
            help="Watch files and run collectstatic if any file changed",
        )
        parser.add_argument(
            "--pycharm-host",
            type=str,
            default=None,
            help="The host of the pycharm debug server",
        )
        parser.add_argument(
            "--pycharm-port",
            type=int,
            default=None,
            help="The port of the pycharm debug server",
        )
        parser.add_argument(
            "--max-body-size",
            type=int,
            default=1024 * 1024 * 100,
            help="The maximum size of the body of a request in bytes",
        )
        parser.add_argument(
            "--max-buffer-size",
            type=int,
            default=1024 * 1024 * 100,
            help="The maximum size of the buffer of a request in bytes",
        )
        parser.add_argument(
            "--mode",
            "--interface",
            dest="mode",
            type=str,
            choices=["auto", "wsgi", "asgi"],
            default="auto",
            help="Execution mode: auto (default), wsgi, or asgi",
        )
        parser.add_argument(
            "--no-fast-404",
            action="store_true",
            default=False,
            help="Disable early fast-404 protection",
        )
        parser.add_argument(
            "--fast-404",
            type=str,
            choices=["auto", "signature", "prefix", "off"],
            default="auto",
            help="Fast-404 protection strategy: auto (default), signature, prefix, or off",
        )
        parser.add_argument(
            "--no-rate-limit",
            action="store_true",
            default=False,
            help="Disable request rate limiter",
        )
        parser.add_argument(
            "--rate-limit",
            type=str,
            default="10/s",
            help="Max allowed requests per second per IP (default: 10/s, or off to disable)",
        )
        parser.add_argument(
            "--rate-limit-burst",
            type=int,
            default=30,
            help="Burst capacity for rate limiter (default: 30)",
        )
        parser.add_argument(
            "--rate-limit-proxy-header",
            type=str,
            default="X-Forwarded-For",
            help="Proxy header to extract client IP from (default: X-Forwarded-For)",
        )

    def merge_option(
        self,
        option_name: str,
        option_descriptor: str,
        options: dict,
        optional: bool = False,
        default: Any = None,
    ):
        if options.get(option_name) is not None and options[option_name] != default:
            return

        try:
            options[option_name] = _get_setting_value(option_descriptor)
            return
        except AttributeError:
            pass

        env_val = _get_env_value(option_descriptor)
        if env_val is not None:
            options[option_name] = env_val
            return

        if options.get(option_name) is None and not optional:
            raise ValueError(
                f"Option {option_descriptor} must be set as environment variable,"
                " in django settings or as a command line argument."
            )

    def merge_options(self, options: dict):
        self.merge_option("static", "HURRICANE_STATIC", options, default=False)
        self.merge_option("media", "HURRICANE_MEDIA", options, default=False)
        self.merge_option("autoreload", "HURRICANE_AUTORELOAD", options, default=False)
        self.merge_option("debug", "HURRICANE_DEBUG", options, default=False)
        self.merge_option("port", "HURRICANE_PORT", options, default=8000)
        self.merge_option("metrics_path", "HURRICANE_METRICS", options, default="/metrics")
        self.merge_option("liveness_probe", "HURRICANE_LIVENESS_PROBE", options, default="/alive")
        self.merge_option("readiness_probe", "HURRICANE_READINESS_PROBE", options, default="/ready")
        self.merge_option("startup_probe", "HURRICANE_STARTUP_PROBE", options, default="/startup")
        self.merge_option("probe_port", "HURRICANE_PROBE_PORT", options, optional=True)
        self.merge_option("req_queue_len", "HURRICANE_REQ_QUEUE_LEN", options, optional=True, default=None)
        if options.get("req_queue_len") is not None:
            options["req_queue_len_explicit"] = True
        else:
            options["req_queue_len"] = 10
            options["req_queue_len_explicit"] = False
        self.merge_option("no_probe", "HURRICANE_NO_PROBE", options, default=False)
        self.merge_option("no_metrics", "HURRICANE_NO_METRICS", options, default=False)
        self.merge_option("command", "HURRICANE_COMMAND", options, optional=True)
        self.merge_option("check_migrations", "HURRICANE_CHECK_MIGRATIONS", options, default=False)
        self.merge_option(
            "check_migrations_apply",
            "HURRICANE_CHECK_MIGRATIONS_APPLY",
            options,
            default=False,
        )
        self.merge_option("debugger", "HURRICANE_DEBUGGER", options, default=False)
        self.merge_option("debugger_port", "HURRICANE_DEBUGGER_PORT", options, default=5678)
        self.merge_option("webhook_url", "HURRICANE_WEBHOOK_URL", options, optional=True)
        self.merge_option(
            "max_lifetime",
            "HURRICANE_MAX_LIFETIME",
            options,
            optional=True,
            default=None,
        )
        self.merge_option("max_memory", "HURRICANE_MAX_MEMORY", options, optional=True, default=None)
        self.merge_option("workers", "HURRICANE_WORKERS", options, optional=True, default=None)
        self.merge_option("static_watch", "HURRICANE_STATIC_WATCH", options, optional=True)
        self.merge_option(
            "pycharm_host",
            "HURRICANE_PYCHARM_HOST",
            options,
            optional=True,
            default=None,
        )
        self.merge_option(
            "pycharm_port",
            "HURRICANE_PYCHARM_PORT",
            options,
            optional=True,
            default=None,
        )
        self.merge_option(
            "max_body_size",
            "HURRICANE_MAX_BODY_SIZE",
            options,
            optional=True,
            default=1024 * 1024 * 100,
        )
        self.merge_option(
            "max_buffer_size",
            "HURRICANE_MAX_BUFFER_SIZE",
            options,
            optional=True,
            default=1024 * 1024 * 100,
        )
        self.merge_option(
            "mode",
            "HURRICANE_MODE",
            options,
            optional=True,
            default="auto",
        )
        # Fallback check for legacy INTERFACE / HURRICANE_INTERFACE
        if options.get("mode") == "auto":
            legacy_interface = getattr(
                settings,
                "HURRICANE_INTERFACE",
                getattr(
                    settings,
                    "INTERFACE",
                    os.environ.get("HURRICANE_INTERFACE", os.environ.get("INTERFACE")),
                ),
            )
            if legacy_interface:
                options["mode"] = legacy_interface
        options["interface"] = options.get("mode", "auto")

    def handle(self, *args, **options):
        self.merge_options(options)

        os.environ["HURRICANE_SHM_NAME"] = f"hurricane_shm_{os.getpid()}_{options.get('port', 8000)}"
        cleanup_shm()

        start_time = time.time()
        if STRUCTLOG_ENABLED:
            logger.info(
                "Granian-powered Django web server.",
                hurricane=HURRICANE_DIST_VERSION,
            )
        else:
            logger.info(f"Granian-powered Django web server. Version: {HURRICANE_DIST_VERSION}")

        if options["autoreload"]:
            if options.get("static_watch"):
                logger.info("Watching static files for any changes")
                for path in options["static_watch"]:
                    if os.path.exists(path):
                        logger.info(f"Watching path {path}.")
                    else:
                        logger.error(f"Tried to watch {path}, but it does not exist.")
            logger.info("Autoreload was performed")

        probe_port = options["probe_port"] if options["probe_port"] else options["port"] + 1
        options["probe_port"] = probe_port

        options, probe_representations = sanitize_probes(options)

        include_probe = False
        probe_server = None
        if not options["no_probe"]:
            if probe_port != options["port"]:
                if STRUCTLOG_ENABLED:
                    self.structlog_probe_configured(probe_port, probe_representations, options)
                else:
                    logger.info(
                        f"Starting probe application running on port {probe_port} with route liveness-probe: "
                        f"{probe_representations['liveness_probe']}, "
                        f"readiness-probe: {probe_representations['readiness_probe']}, "
                        f"startup-probe: {probe_representations['startup_probe']}"
                    )
                self.log_prometheus(options, probe_port)
                probe_server = make_probe_server(options, self.check)
                probe_server.listen(probe_port)
            else:
                include_probe = True
                if STRUCTLOG_ENABLED:
                    self.structlog_probe_configured(probe_port, probe_representations, options)
                else:
                    logger.info(
                        f"Starting probe application with routes "
                        f"liveness-probe: {probe_representations['liveness_probe']}, "
                        f"readiness-probe: {probe_representations['readiness_probe']}, "
                        f"startup-probe: {probe_representations['startup_probe']} "
                        f"running integrated on port {probe_port}"
                    )
                    self.log_prometheus(options, probe_port)
        else:
            if STRUCTLOG_ENABLED:
                logger.info("Probes configured", active=False)
                logger.info(PROMETHEUS_CONFIGURED_EVENT, active=False)
            else:
                logger.info("No probe application running")
                logger.info("Running without Prometheus exporter, because --no-probe flag was set")
            options["no_metrics"] = True

        setup_debugging(options)

        # Determine WSGI vs ASGI mode
        mode = options.get("mode") or options.get("interface") or "auto"
        if mode == "asgi":
            is_asgi = True
        elif mode == "wsgi":
            is_asgi = False
        else:
            is_asgi = bool(getattr(settings, "ASGI_APPLICATION", None))

        if is_asgi and options.get("req_queue_len_explicit"):
            if STRUCTLOG_ENABLED:
                logger.warning(
                    "The '--req-queue-len' option is ignored when running in ASGI mode. "
                    "Event loop lag tracking is used instead for readiness probing.",
                    req_queue_len=options.get("req_queue_len"),
                )
            else:
                logger.warning(
                    f"The '--req-queue-len' option ({options.get('req_queue_len')}) is ignored when running in ASGI mode. "
                    "Event loop lag tracking is used instead for readiness probing."
                )

        configure_granian(
            options=options,
            check_func=self.check,
            is_asgi=is_asgi,
            include_probe=include_probe,
        )

        # Pre-flight tasks execution
        if options.get("command"):
            command_task(
                commands=options["command"],
                webhook_url=options.get("webhook_url") or None,
            )
        if options.get("check_migrations") or options.get("check_migrations_apply"):
            check_db_and_migrations(
                webhook_url=options.get("webhook_url") or None,
                apply_migration=bool(options.get("check_migrations_apply")),
            )

        make_http_server_and_listen(
            start_time=start_time,
            options=options,
            check=self.check,
            include_probe=include_probe,
        )

        if options.get("max_memory"):
            if STRUCTLOG_ENABLED:
                logger.info(
                    "Memory allocation check",
                    max_memory_mb=options["max_memory"],
                    active=True,
                )
            else:
                logger.info(f"Starting memory allocation check with maximum memory set to {options['max_memory']} Mb")

            def mem_monitor():
                restarts = 0
                max_mem = options["max_memory"]
                import psutil

                main_proc = psutil.Process()
                while True:
                    time.sleep(0.5)
                    try:
                        total_bytes = main_proc.memory_info().rss
                        for child in main_proc.children(recursive=True):
                            try:
                                total_bytes += child.memory_info().rss
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                        current_mb = total_bytes / (1024 * 1024)
                        if current_mb > max_mem:
                            restarts += 1
                            if STRUCTLOG_ENABLED:
                                logger.warning(
                                    "Memory (rss) usage is too high. Restarting",
                                    current_mb=current_mb,
                                    maximum_memory_mb=max_mem,
                                    restarts=restarts,
                                    active=True,
                                )
                            else:
                                logger.warning(
                                    f"Memory (rss) usage is too high. Restarting. Current memory usage is {current_mb}MB; "
                                    f"Maximum memory allowed is {max_mem}MB (restart #{restarts})"
                                )
                            break
                    except Exception:
                        break

            threading.Thread(target=mem_monitor, daemon=True).start()
        else:
            if STRUCTLOG_ENABLED:
                logger.warning("Memory allocation check", active=False)
            else:
                logger.warning("Starting without memory allocation check")

        workers = 1
        threads = options.get("workers") or min(32, (os.cpu_count() or 1) + 4)

        reload_paths = None
        if options.get("autoreload") and options.get("static_watch"):
            reload_paths = [p for p in options["static_watch"] if os.path.exists(p)]

        server = Granian(
            target="hurricane.server.granian:get_application",
            factory=True,
            address="0.0.0.0",
            port=options["port"],
            interface=Interfaces.ASGI if is_asgi else Interfaces.WSGI,
            workers=workers,
            blocking_threads=threads,
            runtime_mode="mt",
            backlog=1024,
            log_access=False,
            log_enabled=False,
            reload=bool(options.get("autoreload")),
            reload_paths=reload_paths,
            workers_max_rss=options.get("max_memory"),
        )

        try:
            server.serve()
        except KeyboardInterrupt:
            logger.info("Received signal SIGINT. Shutting down now.")
        finally:
            if probe_server:
                probe_server.stop()
            cleanup_shm()

    def structlog_probe_configured(self, probe_port, probe_representations, options):
        logger.info(
            PROBE_CONFIGURED_EVENT,
            port=probe_port,
            active=True,
            liveness=probe_representations["liveness_probe"],
            readiness=probe_representations["readiness_probe"],
            startup=probe_representations["startup_probe"],
            integrated=probe_port == options["port"],
        )

    def log_prometheus(self, options, probe_port):
        if "no_metrics" not in options or not options["no_metrics"]:
            if STRUCTLOG_ENABLED:
                logger.info(
                    PROMETHEUS_CONFIGURED_EVENT,
                    port=probe_port,
                    route=options["metrics_path"],
                    active=True,
                )
            else:
                logger.info(
                    f"Starting Prometheus metrics exporter on port {probe_port} with route {options['metrics_path']}"
                )
        else:
            if STRUCTLOG_ENABLED:
                logger.info(PROMETHEUS_CONFIGURED_EVENT, active=False)
            else:
                logger.info("Running without Prometheus exporter, because --no-metrics flag was set")
