import asyncio
import functools
import signal
import time
import traceback
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Callable

import tornado.autoreload
import tornado.web
import tornado.wsgi
from django.core.management import call_command
from django.core.management.base import BaseCommand
from tornado.platform.asyncio import AsyncIOMainLoop

from hurricane.metrics import StartupTimeMetric
from hurricane.server import logger, make_http_server, make_probe_server


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
        if options["probe_port"] is None:
            # the probe port by default is supposed to run the next port of the application
            probe_port = options["port"] + 1
        else:
            probe_port = options["probe_port"]

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

        def make_http_server_and_listen(start_time: float) -> None:

            logger.info(f"Starting HTTP Server on port {options['port']}")
            django_application = make_http_server(options, self.check, include_probe)
            django_application.listen(options["port"])
            end_time = time.time()
            time_elapsed = end_time - start_time
            # if startup time metric value is set - startup process is finished
            StartupTimeMetric.set(time_elapsed)
            logger.info(f"Startup time is {time_elapsed} seconds")

        if options["command"]:

            def command_task(
                callback: Callable, main_loop: asyncio.unix_events._UnixSelectorEventLoop, start_time: float
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
                    logger.info(
                        f"Command {command_split[0]} was executed in {end_time_command-start_time_command} seconds"
                    )
                # start http server and listen to it
                main_loop.call_soon_threadsafe(callback, start_time)

            executor = ThreadPoolExecutor(max_workers=1)
            # parameters of command_task are make_http_and_listen as callback and loop as main_loop
            future = loop.run_in_executor(executor, command_task, make_http_server_and_listen, loop, start_time)

            def exception_check_callback(future: asyncio.Future) -> None:
                # checks if there were any exceptions in the executor and if any stops the loop
                if future.exception():
                    logger.error("Execution of command failed")
                    # prints the whole tracestack
                    try:
                        future.result()
                    except Exception:
                        traceback.print_exc()
                    current_loop = asyncio.get_event_loop()
                    current_loop.stop()

            # callback runs after run_in_executor is done
            future.add_done_callback(exception_check_callback)
        else:
            make_http_server_and_listen(start_time=start_time)

        # prepare the io loops
        def ask_exit(signame):
            logger.info(f"Received signal {signame}. Shutting down now.")
            loop.stop()

        for signame in ("SIGINT", "SIGTERM"):
            loop.add_signal_handler(getattr(signal, signame), functools.partial(ask_exit, signame))

        loop.run_forever()
