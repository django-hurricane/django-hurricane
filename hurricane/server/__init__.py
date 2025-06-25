import asyncio
import concurrent.futures
import importlib.metadata
import os
import signal
import sys
import time
import traceback
from typing import Callable, Optional

import psutil  # type: ignore
import tornado
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from tornado.autoreload import _reload

from hurricane.management.commands import HURRICANE_DIST_VERSION
from hurricane.metrics import (
    RequestCounterMetric,
    ResponseTimeAverageMetric,
    StartupTimeMetric,
    registry,
)
from hurricane.server.django import (
    DjangoHandler,
    DjangoLivenessHandler,
    DjangoReadinessHandler,
    DjangoStartupHandler,
    DjangoStaticFilesHandler,
    PrometheusHandler,
)
from hurricane.server.loggers import STRUCTLOG_ENABLED, access_log, logger

if STRUCTLOG_ENABLED:
    from structlog.contextvars import bind_contextvars

EXECUTOR = None
HTTP_CONFIGURED_EVENT = "HTTP configured"


class HurricaneApplication(tornado.web.Application):
    def __init__(self, *args, **kwargs):
        self.collect_metrics = True
        if "metrics" in kwargs:
            self.collect_metrics = kwargs["metrics"]
        global EXECUTOR
        if EXECUTOR is None:
            max_workers = kwargs.get("workers")
            EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.executor = EXECUTOR
        super(HurricaneApplication, self).__init__(*args, **kwargs)

    def log_request(self, handler: tornado.web.RequestHandler) -> None:
        """Writes a completed HTTP request to the logs."""
        if handler.get_status() < 400:
            log_method = access_log.info
        elif handler.get_status() < 500:
            log_method = access_log.warning
        else:
            log_method = access_log.error
        request_time = 1000.0 * handler.request.request_time()
        if STRUCTLOG_ENABLED:
            bind_contextvars(
                hurricane=HURRICANE_DIST_VERSION,
                protocol=handler.request.protocol,
                method=handler.request.method,
                path=handler.request.path,
                status=handler.get_status(),
                request_time=request_time,
                remote_ip=handler.request.remote_ip,
                id=handler.request.headers.get("X-Request-ID", "n/a"),
                traceparent=handler.request.headers.get("traceparent", "n/a"),
            )
            log_method(
                f"TX {handler.request.method} {handler.request.path} {round(request_time, 2)}ms"
            )
        else:
            log_method(
                "%d %s %.2fms",
                handler.get_status(),
                handler._request_summary(),
                request_time,
            )
        if self.collect_metrics:
            RequestCounterMetric.increment()
            ResponseTimeAverageMetric.add_value(request_time)


class HurricaneProbeApplication(HurricaneApplication):
    def log_request(self, handler: tornado.web.RequestHandler) -> None:
        """Writes a completed HTTP probe request to the logs."""
        if getattr(settings, "LOG_PROBES", False):
            super(HurricaneProbeApplication, self).log_request(handler)  # type: ignore
        return


def make_probe_server(options, check_func):
    """create probe route application"""
    handlers = [
        (
            options["liveness_probe"],
            DjangoLivenessHandler,
            {
                "check_handler": check_func,
                "webhook_url": options["webhook_url"],
                "max_lifetime": options["max_lifetime"],
            },
        ),
        (
            options["readiness_probe"],
            DjangoReadinessHandler,
            {
                "check_handler": check_func,
                "req_queue_len": options["req_queue_len"],
                "webhook_url": options["webhook_url"],
            },
        ),
        (options["startup_probe"], DjangoStartupHandler),
    ]
    if with_metrics(options):
        handlers.append((options["metrics_path"], PrometheusHandler))
    return HurricaneProbeApplication(handlers, debug=options["debug"], metrics=False)


def with_metrics(options):
    return "no_metrics" not in options or not options["no_metrics"]


def make_http_server(options, check_func, include_probe=False):
    """create all routes for this application"""
    if include_probe:
        handlers = get_integrated_probe_handler(options, check_func)
    else:
        handlers = []
    # if static file serving is enabled
    handlers = add_static_handler(options, handlers)
    # if media file serving is enabled
    handlers = add_media_handler(options, handlers)

    # append the django routing system
    handlers.append((".*", DjangoHandler))
    return HurricaneApplication(
        handlers,
        debug=options["debug"],
        metrics=not options.get("no_metrics", False),
        workers=options.get("workers"),
    )


def add_media_handler(options, handlers):
    if options["media"]:
        if STRUCTLOG_ENABLED:
            logger.info(
                "Serving media",
                prefix=settings.MEDIA_URL,
                root=settings.MEDIA_ROOT or "",
            )
        else:
            logger.info(
                f"Serving media files under {settings.MEDIA_URL} from {settings.MEDIA_ROOT}"
            )
        handlers.append(
            (
                f"{settings.MEDIA_URL}(.*)",
                tornado.web.StaticFileHandler,
                {"path": settings.MEDIA_ROOT},
            )
        )
    return handlers


def add_static_handler(options, handlers):
    if options["static"]:
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
        if settings.DEBUG and "django.contrib.staticfiles" in settings.INSTALLED_APPS:
            handlers.append(
                (
                    f"{settings.STATIC_URL}(.*)",
                    DjangoStaticFilesHandler,
                )
            )
        else:
            handlers.append(
                (
                    f"{settings.STATIC_URL}(.*)",
                    tornado.web.StaticFileHandler,
                    {"path": settings.STATIC_ROOT},
                )
            )
    return handlers


def get_integrated_probe_handler(options, check_func):
    handlers = [
        (
            options["liveness_probe"],
            DjangoLivenessHandler,
            {
                "check_handler": check_func,
                "webhook_url": options["webhook_url"],
                "max_lifetime": options["max_lifetime"],
            },
        ),
        (
            options["readiness_probe"],
            DjangoReadinessHandler,
            {
                "check_handler": check_func,
                "req_queue_len": options["req_queue_len"],
                "webhook_url": options["webhook_url"],
            },
        ),
        (options["startup_probe"], DjangoStartupHandler),
    ]
    if with_metrics(options):
        handlers.append((options["metrics_path"], PrometheusHandler))
    return handlers


def make_http_server_and_listen(
    start_time: float, options: dict, check: Callable, include_probe: bool
) -> None:
    from hurricane.webhooks import StartupWebhook
    from hurricane.webhooks.base import WebhookStatus

    if not STRUCTLOG_ENABLED:
        logger.info(f"Starting HTTP Server on port {options['port']}")
    django_application = make_http_server(options, check, include_probe)
    django_application.listen(
        options["port"],
        max_body_size=options.get("max_body_size", 1024 * 1024 * 100),
        max_buffer_size=options.get("max_buffer_size", 1024 * 1024 * 100),
    )
    StartupWebhook().run(
        url=options["webhook_url"] or None, status=WebhookStatus.SUCCEEDED
    )
    end_time = time.time()
    time_elapsed = end_time - start_time
    # if startup time metric value is set - startup process is finished
    StartupTimeMetric.set(time_elapsed)
    if with_metrics(options):
        try:
            hurricane_dist_version = importlib.metadata.version("django-hurricane")
        except importlib.metadata.PackageNotFoundError:
            hurricane_dist_version = "unknown"
        registry.metrics["hurricane"].set(
            {
                "version": hurricane_dist_version,
                "startup_time_seconds": str(round(time_elapsed, 5)),
                "server_port": str(options["port"]),
                "serve_static": "true" if options["static"] else "false",
                "serve_media": "true" if options["media"] else "false",
                "probe_port": str(options["probe_port"]),
                "commands": ",".join(
                    [item for row in options.get("command", []) for item in row]
                    if options.get("command")
                    else ""
                ),
            }
        )
    if STRUCTLOG_ENABLED:
        workers = options.get("workers") or min(32, (os.cpu_count() or 1) + 4)
        logger.info(
            HTTP_CONFIGURED_EVENT,
            time=time_elapsed,
            port=options["port"],
            workers=workers,
        )
    else:
        logger.info(f"Startup time is {time_elapsed} seconds")


def command_task(
    commands: list,
    webhook_url: Optional[str] = None,
    loop: Optional[asyncio.unix_events.SelectorEventLoop] = None,
) -> None:
    from hurricane.webhooks import StartupWebhook
    from hurricane.webhooks.base import WebhookStatus

    if not STRUCTLOG_ENABLED:
        logger.info("Starting execution of management commands")
    for command in commands:
        # split a command string to get command options
        command_split = command[0].split()
        if not STRUCTLOG_ENABLED:
            logger.info(
                f"Starting execution of command {command_split[0]} with arguments {command_split[1:]}"
            )
        start_time_command = time.time()
        # call management command
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
            # webhook is registered and run in a new thread, not blocking the process
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
            logger.info(
                f"Command {command_split[0]} was executed in {end_time_command - start_time_command} seconds"
            )


def check_databases():
    for db_name in connections:
        connection = connections[db_name]
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT (1)")
            if STRUCTLOG_ENABLED:
                logger.info("Database check successful", database=db_name)
            else:
                logger.info("Database was checked successfully")
            cursor.close()
            return True
        except Exception as e:
            if STRUCTLOG_ENABLED:
                logger.info("Database check unsuccessful", database=db_name)
            else:
                logger.warning(f"Database command execution has failed with {e}")
            cursor.close()
            return False


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


def signal_handler(signal, frame):
    logger.error("\nprogram exiting gracefully")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def check_db_and_migrations(
    webhook_url: Optional[str] = None,
    loop: Optional[asyncio.unix_events.SelectorEventLoop] = None,
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
    # sanitize probe paths
    options["liveness_probe"] = f"/{options['liveness_probe'].lstrip('/')}".replace(
        " ", ""
    )
    options["readiness_probe"] = f"/{options['readiness_probe'].lstrip('/')}".replace(
        " ", ""
    )
    options["startup_probe"] = f"/{options['startup_probe'].lstrip('/')}".replace(
        " ", ""
    )

    representations = {
        "liveness_probe": options["liveness_probe"],
        "readiness_probe": options["readiness_probe"],
        "startup_probe": options["startup_probe"],
    }
    # adding optional / to the regular expression of probe handler
    options["liveness_probe"] = add_trailing_slash(options, "liveness_probe")
    options["readiness_probe"] = add_trailing_slash(options, "readiness_probe")
    options["startup_probe"] = add_trailing_slash(options, "startup_probe")
    return options, representations


def add_trailing_slash(options, probe_name):
    # adding optional / to the regular expression of probe handler
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
            _reload()
        await asyncio.sleep(10)
