import asyncio
import functools
import time
import traceback
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Callable

import requests
import tornado
from django.conf import settings
from django.core.management import call_command

from hurricane.metrics import RequestCounterMetric, ResponseTimeAverageMetric, StartupTimeMetric
from hurricane.server.django import DjangoHandler, DjangoLivenessHandler, DjangoReadinessHandler, DjangoStartupHandler
from hurricane.server.loggers import access_log, logger


class HurricaneApplication(tornado.web.Application):
    def __init__(self, *args, **kwargs):
        self.collect_metrics = True
        if "metrics" in kwargs:
            self.collect_metrics = kwargs["metrics"]
        super(HurricaneApplication, self).__init__(*args, **kwargs)

    def log_request(self, handler: DjangoHandler) -> None:
        """Writes a completed HTTP request to the logs. """
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
    """ create probe route application """
    handlers = [
        (options["liveness_probe"], DjangoLivenessHandler, {"check_handler": check_func}),
        (options["readiness_probe"], DjangoReadinessHandler, {"req_queue_len": options["req_queue_len"]}),
        (options["startup_probe"], DjangoStartupHandler),
    ]
    return HurricaneApplication(handlers, debug=options["debug"], metrics=False)


def make_http_server(options, check_func, include_probe=False):
    """ create all routes for this application """
    if include_probe:
        handlers = [
            (options["liveness_probe"], DjangoLivenessHandler, {"check_handler": check_func}),
            (options["readiness_probe"], DjangoReadinessHandler, {"check_handler": check_func}),
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


def make_http_server_and_listen(start_time: float, options: dict, check, include_probe) -> None:
    logger.info(f"Starting HTTP Server on port {options['port']}")
    django_application = make_http_server(options, check, include_probe)
    django_application.listen(options["port"])
    end_time = time.time()
    time_elapsed = end_time - start_time
    # if startup time metric value is set - startup process is finished
    StartupTimeMetric.set(time_elapsed)
    logger.info(f"Startup time is {time_elapsed} seconds")


def command_task(
    callback: Callable,
    main_loop: asyncio.unix_events._UnixSelectorEventLoop,
    start_time: float,
    options,
    check,
    include_probe,
) -> None:
    preliminary_commands = options["command"]
    logger.info("Starting execution of management commands")
    for command in preliminary_commands:
        # split a command string to also get command options
        command_split = command[0].split()
        logger.info(f"Starting execution of command {command_split[0]} with arguments {command_split[1:]}")
        # call management command
        start_time_command = time.time()
        call_command(*command_split)
        end_time_command = time.time()
        logger.info(f"Command {command_split[0]} was executed in {end_time_command - start_time_command} seconds")
    # start http server and listen to it
    main_loop.call_soon_threadsafe(callback, start_time, options, check, include_probe)


def send_webhook(data, webhook_url):
    # sending webhook request to the specified url
    logger.info("Start sending webhook")
    response = requests.post(webhook_url, timeout=5, data=data)
    if response.status_code != 200:
        raise ValueError(f"Request to the application returned an error:\n {response.status_code} {response.text}")
    logger.info("Webhook has been sent")


def exception_check_callback_with_webhook(future: asyncio.Future, url: str) -> None:
    # checks if there were any exceptions in the executor and if any stops the loop
    # if exceptions occured, it means, that some or one of the commands have failed
    executor = ThreadPoolExecutor(max_workers=1)
    if future.exception():
        logger.error("Execution of management command has failed")
        # prints the whole tracestack
        try:
            future.result()
        except Exception as e:
            trace = traceback.format_exc()
            logger.error(e)
            logger.error(traceback.print_exc())
        current_loop = asyncio.get_event_loop()
        data = {"startup": "failed", "traceback": trace}
        logger.info("Webhook with a failure status has been initiated")
        fut = current_loop.run_in_executor(executor, send_webhook, data, url)
        fut.add_done_callback(exception_check_callback_webhook)
        current_loop.stop()
    else:
        logger.error("Execution of management commands was successful")
        current_loop = asyncio.get_event_loop()
        data = {"startup": "succeeded"}
        logger.info("Webhook with a success status has been initiated")
        fut = current_loop.run_in_executor(executor, send_webhook, data, url)
        # cb = functools.partial(exception_check_callback_webhook, url=url)
        fut.add_done_callback(exception_check_callback_webhook)


def exception_check_callback_without_webhook(future: asyncio.Future) -> None:
    # checks if there were any exceptions in the executor and if any stops the loop
    # if exceptions occured, it means, that some or one of the commands have failed
    if future.exception():
        logger.error("Execution of management command has failed")
        # prints the whole tracestack
        try:
            future.result()
        except Exception as e:
            logger.error(e)
            logger.error(traceback.print_exc())
            # trace = traceback.format_exc()
        current_loop = asyncio.get_event_loop()
        current_loop.stop()


def exception_check_callback_webhook(future: asyncio.Future, url: str):
    # checks if sending webhook had any failures, it indicates, that command was successfully executed
    # but sending webhook has failed
    if future.exception():
        logger.error(f"Execution of webhook has failed {url}")

        # prints the whole tracestack
        try:
            future.result()
        except Exception as e:
            logger.error(e)
            logger.error(traceback.print_exc())
