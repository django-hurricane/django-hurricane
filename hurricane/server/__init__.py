import asyncio
import importlib.metadata
import os
import signal
import sys
import threading
import time
import traceback
from typing import Any, Callable, Dict, Optional
from wsgiref.simple_server import WSGIServer, make_server

import psutil  # type: ignore
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from granian import Granian
from granian.constants import Interfaces

from hurricane.management.commands import HURRICANE_DIST_VERSION
from hurricane.metrics import (
    RequestCounterMetric,
    ResponseTimeAverageMetric,
    StartupTimeMetric,
    registry,
)
from hurricane.server.gateway import HurricaneASGIGateway, HurricaneWSGIGateway
from hurricane.server.granian import configure_granian, get_probe_application
from hurricane.server.loggers import STRUCTLOG_ENABLED, access_log, logger

if STRUCTLOG_ENABLED:
    from structlog.contextvars import bind_contextvars

HTTP_CONFIGURED_EVENT = "HTTP configured"
PROBE_CONFIGURED_EVENT = "Probe configured"
PROMETHEUS_CONFIGURED_EVENT = "Prometheus configured"


class ReusableWSGIServer(WSGIServer):
    allow_reuse_address = True


class HurricaneProbeServer:
    """
    Lightweight probe server for serving probes and metrics on a separate probe port.
    """

    def __init__(self, options: Dict[str, Any], check_func: Optional[Callable] = None):
        self.options = options
        self.check_func = check_func
        self.server: Optional[WSGIServer] = None
        self.thread: Optional[threading.Thread] = None

    def listen(self, port: int):
        app = get_probe_application()
        self.server = make_server("0.0.0.0", port, app, server_class=ReusableWSGIServer)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        if self.server:
            self.server.shutdown()
            try:
                self.server.server_close()
            except Exception:
                pass


def make_probe_server(options: Dict[str, Any], check_func: Optional[Callable] = None):
    configure_granian(options=options, check_func=check_func, include_probe=True)
    return HurricaneProbeServer(options, check_func)


class HurricaneApplication:
    """
    Backward-compatible application wrapper representing the Hurricane Gateway.
    """

    def __init__(self, *args, **kwargs):
        self.options = kwargs.get("options", {})
        self.check_func = kwargs.get("check_func")
        self.collect_metrics = not self.options.get("no_metrics", False)
        self.gateway = HurricaneWSGIGateway(
            options=self.options,
            check_func=self.check_func,
            include_probe=kwargs.get("include_probe", True),
        )

    def __call__(self, environ, start_response):
        return self.gateway(environ, start_response)


class HurricaneProbeApplication(HurricaneApplication):
    pass


def with_metrics(options: Dict[str, Any]) -> bool:
    return "no_metrics" not in options or not options["no_metrics"]


def make_http_server(options: Dict[str, Any], check_func: Optional[Callable] = None, include_probe: bool = False):
    return HurricaneApplication(options=options, check_func=check_func, include_probe=include_probe)


def make_http_server_and_listen(
    start_time: float,
    options: dict,
    check: Callable,
    include_probe: bool,
) -> None:
    from hurricane.webhooks import StartupWebhook
    from hurricane.webhooks.base import WebhookStatus

    add_static_handler(options, None)
    add_media_handler(options, None)

    if not STRUCTLOG_ENABLED:
        logger.info(f"Starting HTTP Server on port {options['port']}")

    StartupWebhook().run(url=options.get("webhook_url") or None, status=WebhookStatus.SUCCEEDED)
    end_time = time.time()
    time_elapsed = end_time - start_time
    StartupTimeMetric.set(time_elapsed)

    if with_metrics(options):
        try:
            hurricane_dist_version = importlib.metadata.version("django-hurricane")
        except importlib.metadata.PackageNotFoundError:
            hurricane_dist_version = "unknown"
        if "hurricane" in registry.metrics:
            registry.metrics["hurricane"].set(
                {
                    "version": hurricane_dist_version,
                    "startup_time_seconds": str(round(time_elapsed, 5)),
                    "server_port": str(options["port"]),
                    "serve_static": "true" if options.get("static") else "false",
                    "serve_media": "true" if options.get("media") else "false",
                    "probe_port": str(options.get("probe_port")),
                    "commands": ",".join(
                        [item for row in options.get("command", []) for item in row] if options.get("command") else ""
                    ),
                }
            )

    workers = options.get("workers") or min(32, (os.cpu_count() or 1) + 4)
    if STRUCTLOG_ENABLED:
        logger.info(
            HTTP_CONFIGURED_EVENT,
            time=time_elapsed,
            port=options["port"],
            workers=workers,
        )
    else:
        logger.info(f"Startup time is {time_elapsed} seconds")


def add_media_handler(options: Dict[str, Any], handlers: Any):
    if options.get("media"):
        if STRUCTLOG_ENABLED:
            logger.info(
                "Serving media",
                prefix=settings.MEDIA_URL,
                root=settings.MEDIA_ROOT or "",
            )
        else:
            logger.info(f"Serving media files under {settings.MEDIA_URL} from {settings.MEDIA_ROOT}")
    return handlers


def add_static_handler(options: Dict[str, Any], handlers: Any):
    if options.get("static"):
        if STRUCTLOG_ENABLED:
            logger.info(
                "Serving statics",
                prefix=settings.STATIC_URL,
                root=settings.STATIC_ROOT or "",
            )
        else:
            logger.info(
                f"Serving static files under {settings.STATIC_URL} from "
                f"{settings.STATIC_ROOT or '<STATIC_ROOT not set>'}"
            )
    return handlers


def command_task(
    commands: list,
    webhook_url: Optional[str] = None,
    loop: Optional[Any] = None,
) -> None:
    from hurricane.webhooks import StartupWebhook
    from hurricane.webhooks.base import WebhookStatus

    if not STRUCTLOG_ENABLED:
        logger.info("Starting execution of management commands")
    for command in commands:
        command_split = command[0].split()
        if not STRUCTLOG_ENABLED:
            logger.info(f"Starting execution of command {command_split[0]} with arguments {command_split[1:]}")
        start_time_command = time.time()
        try:
            call_command(*command_split)
        except Exception as e:
            logger.error(e)
            error_trace = traceback.format_exc()
            if STRUCTLOG_ENABLED:
                logger.info(
                    "Webhook",
                    url=webhook_url or None,
                    error_trace=error_trace,
                    status=WebhookStatus.FAILED,
                )
            else:
                logger.info("Webhook with a status failed has been initiated")
            StartupWebhook().run(
                url=webhook_url or None,
                error_trace=error_trace,
                close_loop=True,
                status=WebhookStatus.FAILED,
                loop=loop,
            )
            raise e

        end_time_command = time.time()
        if STRUCTLOG_ENABLED:
            logger.info(
                "Command executed",
                command=command_split,
                time=end_time_command - start_time_command,
            )
        else:
            logger.info(f"Command {command_split[0]} was executed in {end_time_command - start_time_command} seconds")


def check_databases() -> bool:
    for db_name in connections:
        connection = connections[db_name]
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT (1)")
            if STRUCTLOG_ENABLED:
                logger.info("Database check successful", database=db_name)
            else:
                logger.info("Database was checked successfully")
        except Exception as e:
            if STRUCTLOG_ENABLED:
                logger.info("Database check unsuccessful", database=db_name)
            else:
                logger.warning(f"Database command execution has failed with {e}")
            return False
    return True


def count_migrations():
    number_of_migrations = 0
    for db_name in connections:
        connection = connections[db_name]
        if hasattr(connection, "prepare_database"):
            connection.prepare_database()
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        number_of_migrations += len(executor.migration_plan(targets))
    return number_of_migrations


def signal_handler(sig, frame):
    logger.error("\nprogram exiting gracefully")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def check_db_and_migrations(
    webhook_url: Optional[str] = None,
    loop: Optional[Any] = None,
    apply_migration: bool = False,
):
    from hurricane.webhooks import StartupWebhook
    from hurricane.webhooks.base import WebhookStatus

    try:
        while check_databases():
            number_of_migrations = count_migrations()
            logger.info(f"There are {number_of_migrations} pending migrations")
            if number_of_migrations == 0:
                logger.info("No pending migrations")
                break
            elif not apply_migration:
                logger.info("Migrations are pending")
                time.sleep(1)

            if apply_migration:
                logger.info("Applying migrations")
                call_command("migrate")

    except Exception as e:
        error_trace = traceback.format_exc()
        if STRUCTLOG_ENABLED:
            logger.info(
                "Webhook",
                url=webhook_url or None,
                error_trace=error_trace,
                status=WebhookStatus.WARNING,
            )
        else:
            logger.info("Webhook with a status warning has been initiated")

        StartupWebhook().run(
            url=webhook_url or None,
            error_trace=error_trace,
            close_loop=True,
            status=WebhookStatus.WARNING,
            loop=loop,
        )
        raise e


def sanitize_probes(options):
    options["liveness_probe"] = f"/{options['liveness_probe'].lstrip('/')}".replace(" ", "")
    options["readiness_probe"] = f"/{options['readiness_probe'].lstrip('/')}".replace(" ", "")
    options["startup_probe"] = f"/{options['startup_probe'].lstrip('/')}".replace(" ", "")

    representations = {
        "liveness_probe": options["liveness_probe"],
        "readiness_probe": options["readiness_probe"],
        "startup_probe": options["startup_probe"],
    }
    options["liveness_probe"] = add_trailing_slash(options, "liveness_probe")
    options["readiness_probe"] = add_trailing_slash(options, "readiness_probe")
    options["startup_probe"] = add_trailing_slash(options, "startup_probe")
    return options, representations


def add_trailing_slash(options, probe_name):
    probe = options[probe_name]
    if probe[-1] == "/":
        return probe + "{0,1}"
    else:
        return probe + "/{0,1}"


def static_watch():
    try:
        logger.info("Collecting static as static file changed")
        call_command("collectstatic", interactive=False, clear=True)
    except Exception as e:
        logger.error(e)


async def check_mem_allocations(maximum_memory: int):
    restarts = 0
    while True:
        current = psutil.Process().memory_info().rss / (1024 * 1024)
        logger.debug(f"Current virtual memory usage is {current}MB")
        current_mb = current
        if current_mb > maximum_memory:
            restarts += 1
            if STRUCTLOG_ENABLED:
                logger.warning(
                    "Memory (rss) usage is too high. Restarting",
                    current_mb=current_mb,
                    maximum_memory_mb=maximum_memory,
                    restarts=restarts,
                )
            else:
                logger.warning(
                    f"Memory (rss) usage is too high. Restarting. Current memory usage is {current_mb}MB; "
                    f"Maximum memory allowed is {maximum_memory}MB (restart #{restarts})"
                )
            # Send SIGHUP to trigger reload
            os.kill(os.getpid(), signal.SIGHUP)
        await asyncio.sleep(10)
