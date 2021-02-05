import asyncio
import functools
import signal
from concurrent.futures.thread import ThreadPoolExecutor
import tornado.autoreload
import tornado.web
import tornado.wsgi
from django.core.management.base import BaseCommand
from django.core.management import call_command
from hurricane.metrics import StartupTimeMetric
import time
from tornado.platform.asyncio import AsyncIOMainLoop

from hurricane.server import logger, make_http_server, make_probe_server


class Command(BaseCommand):
    help = "Start a Tornado-powered Django web server"

    def add_arguments(self, parser):
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
            help="The exposed path (default is /ready) for probes to check readyness",
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
        parser.add_argument("--no-probe", action="store_true", help="Disable probe endpoint")
        parser.add_argument("--no-metrics", action="store_true", help="Disable metrics collection")
        parser.add_argument("--command", type=str, action="append", nargs="+")

    def handle(self, *args, **options):
        start_time = time.time()
        logger.info(f"Starting a Tornado-powered Django web server on port {options['port']}.")

        if options["autoreload"]:
            tornado.autoreload.start()

        # set the probe port
        if options["probe_port"] is None:
            # the probe port by default is supposed to run the next port of the application
            probe_port = options["port"] + 1
        else:
            probe_port = options["probe_port"]

        # sanitize probe path
        if options["liveness_probe"][0] != "/":
            options["liveness_probe"] = "/" + options["liveness_probe"]

        if options["readiness_probe"][0] != "/":
            options["readiness_probe"] = "/" + options["readiness_probe"]

        if options["startup_probe"][0] != "/":
            options["startup_probe"] = "/" + options["startup_probe"]

        # set the probe routes
        # if the probe port is set to the application's port, include it to the application's routes
        include_probe = False
        if not options["no_probe"]:
            if probe_port != options["port"]:
                logger.info(
                    f"Probe application running on port {probe_port} with route {options['liveness_probe']}, "
                    f"{options['readiness_probe']}, {options['startup_probe']}"
                )
                probe_application = make_probe_server(options, self.check)
                probe_application.listen(probe_port)
            else:
                include_probe = True
                logger.info(
                    f"Probe application with routes {options['liveness_probe']}, {options['readiness_probe']}, "
                    f"{options['startup_probe']} running integrated on port {probe_port}"
                )

        else:
            logger.info("No probe application running")

        loop = asyncio.get_event_loop()

        def make_http_server_and_listen(start_time):

            logger.info("Started HTTP Server")
            django_application = make_http_server(options, self.check, include_probe)
            django_application.listen(options["port"])
            end_time = time.time()
            time_elapsed = end_time - start_time
            # if startup time metric value is set - startup process is finished
            StartupTimeMetric.set(time_elapsed)
            logger.info(f"Startup time is {time_elapsed}")

        if options["command"]:

            def command_task(callback, main_loop, start_time):
                command_loop = asyncio.new_event_loop()
                preliminary_commands = options["command"]
                logger.info("Started execution of management commands")
                for command in preliminary_commands:
                    # split a command string to also get command options
                    command_split = command[0].split()
                    # call management command
                    call_command(*command_split)
                command_loop.close()
                # start http server and listen to it
                main_loop.call_soon_threadsafe(callback, start_time)

            executor = ThreadPoolExecutor(max_workers=1)
            # parameters of command_task are make_http_and_listen as callback and loop as main_loop
            future = loop.run_in_executor(executor, command_task, make_http_server_and_listen, loop, start_time)

            def exception_check_callback(future):
                # checks if there were any exceptions in the executor and if any stops the loop
                if future.exception():
                    logger.error(future.exception())
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
