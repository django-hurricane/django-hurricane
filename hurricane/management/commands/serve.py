import asyncio
import functools
import signal
import time
import traceback
from concurrent.futures.thread import ThreadPoolExecutor

import tornado.autoreload
import tornado.web
import tornado.wsgi
from django.core.management.base import BaseCommand

from hurricane.server import (
    check_db_and_migrations,
    command_task,
    logger,
    make_http_server_and_listen,
    make_probe_server,
)
from hurricane.webhooks import StartupWebhook
from hurricane.webhooks.base import WebhookStatus


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
        - ``--check-migrations`` - check if all migrations were applied before starting application
        - ``--webhook-url``- If specified, webhooks will be sent to this url
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
        parser.add_argument("--check-migrations", action="store_true", help="Check if migrations were applied")
        parser.add_argument(
            "--webhook-url",
            type=str,
            help="Url for webhooks",
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
            logger.info("Autoreload was performed")

        # set the probe port
        # the probe port by default is supposed to run the next port of the application
        probe_port = options["probe_port"] if options["probe_port"] else options["port"] + 1

        # sanitize probe paths
        options["liveness_probe"] = f"/{options['liveness_probe'].lstrip('/')}"
        options["readiness_probe"] = f"/{options['readiness_probe'].lstrip('/')}"
        options["startup_probe"] = f"/{options['startup_probe'].lstrip('/')}"

        # set the probe routes
        # if probe port is set to the application's port, add it to the application's routes
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

        make_http_server_wrapper = functools.partial(
            make_http_server_and_listen,
            start_time=start_time,
            options=options,
            check=self.check,
            include_probe=include_probe,
        )

        # all commands, that should be executed before starting http server should be added to this list
        exec_list = []
        if options["command"]:
            # wrap function to use additional variables
            management_commands_wrapper = functools.partial(
                command_task,
                commands=options["command"],
                webhook_url=options["webhook_url"] or None,
                loop=loop,
            )
            exec_list.append(management_commands_wrapper)
        if options["check_migrations"]:
            check_db_and_migrations_wrapper = functools.partial(
                check_db_and_migrations, webhook_url=options["webhook_url"] or None, loop=loop
            )
            exec_list.append(check_db_and_migrations_wrapper)

        def bundle_func(exec_list, loop, make_http_server_wrapper):
            # executes functions from exec_list sequentially
            for func in exec_list:
                func(*args)
            # after all functions were executed http server is started in the main thread
            # call_soon_threadsafe puts http server into the main loop of the program
            loop.call_soon_threadsafe(make_http_server_wrapper)

        executor = ThreadPoolExecutor(max_workers=1)
        # bundle_func is executed in a separate thread. Main thread has an active probe server, which should not be
        # interrupted
        loop.run_in_executor(executor, bundle_func, exec_list, loop, make_http_server_wrapper)

        def ask_exit(signame):
            logger.info(f"Received signal {signame}. Shutting down now.")
            loop.stop()

        for signame in ("SIGINT", "SIGTERM"):
            loop.add_signal_handler(getattr(signal, signame), functools.partial(ask_exit, signame))

        loop.run_forever()
