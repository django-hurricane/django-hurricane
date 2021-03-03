import asyncio
import functools
import signal
import time
from concurrent.futures.thread import ThreadPoolExecutor

import tornado.autoreload
import tornado.web
import tornado.wsgi
from django.core.management.base import BaseCommand

from hurricane.server import (
    command_task,
    exception_check_callback_webhook,
    exception_check_callback_with_webhook,
    exception_check_callback_without_webhook,
    logger,
    make_http_server_and_listen,
    make_probe_server,
    send_webhook,
)


class Command(BaseCommand):

    """
    Start a Tornado-powered Django web server.
    Implements serve command as a management command for django application.
    The new command can be called using ``python manage.py server <arguments>``.
    It also can take command arguments, which are python django management commands and will be executed asynchronously.
    Upon successful execution of management commands, application server will be started. During execution of management
    commands probe server can be polled, in particular startup probe, which will respond with a status 400.
    Arguments:
        - ``--static`` - serve collected static files
        - ``--media`` - serve media files
        - ``--autoreload`` - reload code on change
        - ``--debug`` - set Tornado's Debug flag
        - ``--port`` - the port for Tornado to listen on
        - ``--startup-probe`` - the exposed path (default is /startup) for probes to check startup
        - ``--readiness-probe`` - the exposed path (default is /ready) for probes to check readiness
        - ``--liveness-probe`` - the exposed path (default is /alive) for probes to check liveness
        - ``--probe-port`` - the port for Tornado probe route to listen on
        - ``--req-queue-len`` - threshold of length of queue of request, which is considered for readiness probe
        - ``--no-probe`` - disable probe endpoint
        - ``--no-metrics`` - disable metrics collection
        - ``--command`` - repetitive command for adding execution of management commands before serving
        - ``--webhook-url``- url, which is used for sending webhook request
    """

    help = "Start a Tornado-powered Django web server"

    def add_arguments(self, parser):
        """
        Defines arguments, that can be accepted with ``serve`` command.
        """
        parser.add_argument("--static", action="store_true", help="Serve collected static files")
        parser.add_argument("--media", action="store_true", help="Serve media files")
        parser.add_argument("--autoreload", action="store_true", help="Reload code on change")
        parser.add_argument("--debug", action="store_true", help="Set Tornado's Debug flag")
        parser.add_argument("--port", type=int, default=8000, help="The port for Tornado to listen on")
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
            help="The port for Tornado probe route to listen on",
        )
        parser.add_argument("--req-queue-len", type=int, default=10, help="Length of the request queue")
        parser.add_argument("--no-probe", action="store_true", help="Disable probe endpoint")
        parser.add_argument("--no-metrics", action="store_true", help="Disable metrics collection")
        parser.add_argument("--command", type=str, action="append", nargs="+")
        parser.add_argument(
            "--startup-webhook",
            type=str,
            help="Url for startup webhook",
        )
        parser.add_argument(
            "--readiness-webhook",
            type=str,
            help="Url for readiness webhook",
        )

    def handle(self, *args, **options):
        """
        Defines functionalities for different arguments. After all arguments were processed, it starts the async event
        loop.
        """
        start_time = time.time()
        logger.info("Tornado-powered Django web server")

        if options["autoreload"]:
            tornado.autoreload.start()

        # set the probe port
        # the probe port by default is supposed to run the next port of the application
        probe_port = options["probe_port"] if options["probe_port"] else options["port"] + 1

        # sanitize probe paths
        options["liveness_probe"] = f"/{options['liveness_probe'].lstrip('/')}"
        options["readiness_probe"] = f"/{options['readiness_probe'].lstrip('/')}"
        options["startup_probe"] = f"/{options['startup_probe'].lstrip('/')}"

        # set the probe routes
        # if the probe port is set to the application's port, include it to the application's routes
        include_probe = False
        if not options["no_probe"]:
            if probe_port != options["port"]:
                logger.info(
                    f"Starting probe application running on port {probe_port} with route liveness-probe: "
                    f"{options['liveness_probe']}, readiness-probe: {options['readiness_probe']}, "
                    f"startup-probe: {options['startup_probe']}"
                )
                probe_application = make_probe_server(options, self.check)
                probe_application.listen(probe_port)

            else:
                include_probe = True
                logger.info(
                    f"Starting probe application with routes liveness-probe: {options['liveness_probe']}, "
                    f"readiness-probe: {options['readiness_probe']}, startup-probe: {options['startup_probe']} "
                    f"running integrated on port {probe_port}"
                )

        else:
            logger.info("No probe application running")

        loop = asyncio.get_event_loop()

        if options["command"]:
            executor = ThreadPoolExecutor(max_workers=1)
            # parameters of command_task are make_http_and_listen as callback and loop as main_loop
            future = loop.run_in_executor(
                executor,
                command_task,
                make_http_server_and_listen,
                loop,
                start_time,
                options,
                self.check,
                include_probe,
            )
            # callback runs after run_in_executor is done
            if options["startup_webhook"]:
                cb = functools.partial(exception_check_callback_with_webhook, url=options["startup_webhook"])
                future.add_done_callback(cb)
            else:
                cb = functools.partial(exception_check_callback_without_webhook, url=options["startup_webhook"])
                future.add_done_callback(cb)
        else:
            make_http_server_and_listen(start_time, options, self.check, include_probe)
            if options["startup_webhook"]:
                current_loop = asyncio.get_event_loop()
                executor = ThreadPoolExecutor(max_workers=1)
                data = {"startup": "succeeded"}
                fut = current_loop.run_in_executor(executor, send_webhook, data, options["startup_webhook"])
                # callback runs after run_in_executor is done
                cb = functools.partial(exception_check_callback_webhook, url=options["startup_webhook"])
                fut.add_done_callback(cb)

        # prepare the io loops
        def ask_exit(signame):
            logger.info(f"Received signal {signame}. Shutting down now.")
            loop.stop()

        for signame in ("SIGINT", "SIGTERM"):
            loop.add_signal_handler(getattr(signal, signame), functools.partial(ask_exit, signame))

        loop.run_forever()
