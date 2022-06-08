import asyncio
import signal
import sys
import time
import traceback
from typing import Callable

import tornado
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

from hurricane.metrics import RequestCounterMetric, ResponseTimeAverageMetric, StartupTimeMetric
from hurricane.server.django import DjangoHandler, DjangoLivenessHandler, DjangoReadinessHandler, DjangoStartupHandler
from hurricane.server.loggers import access_log, logger
from hurricane.webhooks import StartupWebhook
from hurricane.webhooks.base import WebhookStatus


class HurricaneApplication(tornado.web.Application):
    def __init__(self, *args, **kwargs):
        self.collect_metrics = True
        if "metrics" in kwargs:
            self.collect_metrics = kwargs["metrics"]
        super(HurricaneApplication, self).__init__(*args, **kwargs)

    def log_request(self, handler: DjangoHandler) -> None:
        """Writes a completed HTTP request to the logs."""
        if handler.get_status() < 400:
            log_method = access_log.info
        elif handler.get_status() < 500:
            log_method = access_log.warning
        else:
            log_method = access_log.error
        request_time = 1000.0 * handler.request.request_time()
        log_method(
            "%d %s %.2fms",
            handler.get_status(),
            handler._request_summary(),
            request_time,
        )
        if self.collect_metrics:
            RequestCounterMetric.increment()
            ResponseTimeAverageMetric.add_value(request_time)


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
    return HurricaneApplication(handlers, debug=options["debug"], metrics=False)


def make_http_server(options, check_func, include_probe=False):
    """create all routes for this application"""
    if include_probe:
        handlers = [
            (
                options["liveness_probe"],
                DjangoLivenessHandler,
                {"check_handler": check_func, "webhook_url": options["webhook_url"]},
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
    else:
        handlers = []
    # if static file serving is enabled
    if options["static"]:
        logger.info(f"Serving static files under {settings.STATIC_URL} from {settings.STATIC_ROOT}")
        handlers.append(
            (
                f"{settings.STATIC_URL}(.*)",
                tornado.web.StaticFileHandler,
                {"path": settings.STATIC_ROOT},
            )
        )
    # if media file serving is enabled
    if options["media"]:
        logger.info(f"Serving media files under {settings.MEDIA_URL} from {settings.MEDIA_ROOT}")
        handlers.append(
            (
                f"{settings.MEDIA_URL}(.*)",
                tornado.web.StaticFileHandler,
                {"path": settings.MEDIA_ROOT},
            )
        )

    # append the django routing system
    handlers.append((".*", DjangoHandler))
    return HurricaneApplication(handlers, debug=options["debug"], metrics=not options["no_metrics"])


def make_http_server_and_listen(start_time: float, options: dict, check: Callable, include_probe: bool) -> None:
    logger.info(f"Starting HTTP Server on port {options['port']}")
    django_application = make_http_server(options, check, include_probe)
    django_application.listen(options["port"])
    StartupWebhook().run(url=options["webhook_url"] or None, status=WebhookStatus.SUCCEEDED)
    end_time = time.time()
    time_elapsed = end_time - start_time
    # if startup time metric value is set - startup process is finished
    StartupTimeMetric.set(time_elapsed)
    logger.info(f"Startup time is {time_elapsed} seconds")


def command_task(commands: list, webhook_url: str = None, loop: asyncio.unix_events.SelectorEventLoop = None) -> None:
    logger.info("Starting execution of management commands")
    for command in commands:

        # split a command string to get command options
        command_split = command[0].split()
        logger.info(f"Starting execution of command {command_split[0]} with arguments {command_split[1:]}")
        start_time_command = time.time()
        # call management command
        try:
            call_command(*command_split)
        except Exception as e:
            logger.error(e)
            error_trace = traceback.format_exc()
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

        logger.info(f"Command {command_split[0]} was executed in {end_time_command - start_time_command} seconds")


def check_databases():
    for db_name in connections:
        connection = connections[db_name]
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT (1)")
            logger.info("Database was checked successfully")
            cursor.close()
            return True
        except Exception as e:
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


def check_db_and_migrations(webhook_url: str = None, loop: asyncio.unix_events.SelectorEventLoop = None):
    try:
        while check_databases():
            number_of_migrations = count_migrations()

            logger.info(f"There are {number_of_migrations} pending migrations")
            if number_of_migrations == 0:
                logger.info("No pending migrations")
                break

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.info("Webhook with a status warning has been initiated")

        StartupWebhook().run(
            url=webhook_url or None, error_trace=error_trace, close_loop=True, status=WebhookStatus.WARNING, loop=loop
        )
        raise e


def sanitize_probes(options):

    # sanitize probe paths
    options["liveness_probe"] = f"/{options['liveness_probe'].lstrip('/')}".replace(" ", "")
    options["readiness_probe"] = f"/{options['readiness_probe'].lstrip('/')}".replace(" ", "")
    options["startup_probe"] = f"/{options['startup_probe'].lstrip('/')}".replace(" ", "")

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
