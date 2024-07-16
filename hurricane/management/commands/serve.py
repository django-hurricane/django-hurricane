import asyncio
import functools
import os
import signal
import time
from concurrent.futures.thread import ThreadPoolExecutor

import tornado.autoreload
import tornado.web
import tornado.wsgi
from django.conf import settings
from django.core.management.base import BaseCommand

from hurricane.management.commands import HURRICANE_DIST_VERSION
from hurricane.server import (
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
from hurricane.server.loggers import STRUCTLOG_ENABLED

PROBE_CONFIGURED_EVENT = "Probe configured"
PROMETHEUS_CONFIGURED_EVENT = "Prometheus configured"


class Command(BaseCommand):

    """
    Start a Tornado-powered Django web server by using ``python manage.py serve <arguments>``.

    It can run Django management commands with the ``--command`` flag, that will be executed asynchronously.
    The application server will only be started upon successful execution of management commands. During execution
    of management commands the startup probe responds with a status 400.

    Arguments:
        - ``--static`` - serve collected static files
        - ``--media`` - serve media files
        - ``--autoreload`` - reload code on change
        - ``--debug`` - set Tornado's Debug flag
        - ``--port`` - the port for Tornado to listen on
        - ``--metrics`` - the exposed path (default is /metrics) to export Prometheus metrics
        - ``--startup-probe`` - the exposed path (default is /startup) for probes to check startup
        - ``--readiness-probe`` - the exposed path (default is /ready) for probes to check readiness
        - ``--liveness-probe`` - the exposed path (default is /alive) for probes to check liveness
        - ``--probe-port`` - the port for Tornado probe route to listen on
        - ``--req-queue-len`` - threshold of length of queue of request, which is considered for readiness probe
        - ``--no-probe`` - disable probe endpoint
        - ``--no-metrics`` - disable metrics collection
        - ``--command`` - repetitive command for adding execution of management commands before serving
        - ``--check-migrations`` - check if all migrations were applied before starting application
        - ``--check-migrations-apply`` - same as --check-migrations but also applies them if needed
        - ``--webhook-url``- If specified, webhooks will be sent to this url
        - ``--max-lifetime``- If specified,  maximum requests after which pod is restarted
        - ``--max-memory``- If specified, process reloads after exceeding maximum memory (RSS) usage (in Mb)
        - ``--static-watch`` - If specified, static files will be watched for changes and recollected
        - ``--max-body-size`` - The maximum size of the body of a tornado request in bytes
        - ``--max-buffer-size`` - The maximum size of the buffer of a tornado request in bytes
    """

    help = "Start a Tornado-powered Django web server"

    def add_arguments(self, parser):
        """
        Defines arguments, that can be accepted with ``serve`` command.
        """
        parser.add_argument(
            "--static", action="store_true", help="Serve collected static files"
        )
        parser.add_argument("--media", action="store_true", help="Serve media files")
        parser.add_argument(
            "--autoreload", action="store_true", help="Reload code on change"
        )
        parser.add_argument(
            "--debug", action="store_true", help="Set Tornado's Debug flag"
        )
        parser.add_argument(
            "--port", type=int, default=8000, help="The port for Tornado to listen on"
        )
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
            help="The port for Tornado probe route to listen on",
        )
        parser.add_argument(
            "--req-queue-len", type=int, default=10, help="Length of the request queue"
        )
        parser.add_argument(
            "--no-probe", action="store_true", help="Disable probe endpoint"
        )
        parser.add_argument(
            "--no-metrics", action="store_true", help="Disable metrics collection"
        )
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

    def merge_option(
        self,
        option_name: str,
        option_descriptor: str,
        options: dict,
        optional=False,
        default=None,
    ):
        """
        Merges a single option into the given option dictionary

        Args:
            option_name (str): Name of the option in the options dictionary
            option_descriptor (str): Name of the option as env variable
        """
        # leave early if option is already set via cli argument - highest precedence
        if options[option_name] is not None and options[option_name] != default:
            return
        try:  # first try to add option from django settings - second highest precedence
            options.update(
                {
                    option_name: getattr(
                        settings, option_descriptor.removeprefix("HURRICANE_")
                    )
                }
            )
        except AttributeError:  # then add from env variables - lowest precedence
            if option_descriptor not in os.environ and options[option_name] is None:
                if optional:  # if optional, just return and do not raise an error
                    return
                raise ValueError(
                    (
                        f"Option {option_descriptor} must be set as environment variable,"
                        " in django settings or as a command line argument."
                    )
                )
            # try parsing int in general because we can't know the type of env vars
            try:
                options.update(
                    {option_name: int(str(os.environ.get(option_descriptor)))}
                )
            except (TypeError, ValueError):
                options.update(
                    {
                        option_name: os.environ.get(option_descriptor)
                        if option_descriptor in os.environ
                        else options[option_name]
                    }
                )

    def merge_options(self, options: dict):
        """
        Merges options with django settings. Precedence is the following:
        - ENV variables
        - Django settings
        - Command line arguments
        """
        self.merge_option("static", "HURRICANE_STATIC", options, default=False)
        self.merge_option("media", "HURRICANE_MEDIA", options, default=False)
        self.merge_option("autoreload", "HURRICANE_AUTORELOAD", options, default=False)
        self.merge_option("debug", "HURRICANE_DEBUG", options, default=False)
        self.merge_option("port", "HURRICANE_PORT", options, default=8000)
        self.merge_option(
            "metrics_path", "HURRICANE_METRICS", options, default="/metrics"
        )
        self.merge_option(
            "liveness_probe", "HURRICANE_LIVENESS_PROBE", options, default="/alive"
        )
        self.merge_option(
            "readiness_probe", "HURRICANE_READINESS_PROBE", options, default="/ready"
        )
        self.merge_option(
            "startup_probe", "HURRICANE_STARTUP_PROBE", options, default="/startup"
        )
        self.merge_option("probe_port", "HURRICANE_PROBE_PORT", options, optional=True)
        self.merge_option(
            "req_queue_len", "HURRICANE_REQ_QUEUE_LEN", options, default=10
        )
        self.merge_option("no_probe", "HURRICANE_NO_PROBE", options, default=False)
        self.merge_option("no_metrics", "HURRICANE_NO_METRICS", options, default=False)
        self.merge_option("command", "HURRICANE_COMMAND", options, optional=True)
        self.merge_option(
            "check_migrations", "HURRICANE_CHECK_MIGRATIONS", options, default=False
        )
        self.merge_option(
            "check_migrations_apply",
            "HURRICANE_CHECK_MIGRATIONS_APPLY",
            options,
            default=False,
        )
        self.merge_option("debugger", "HURRICANE_DEBUGGER", options, default=False)
        self.merge_option(
            "debugger_port", "HURRICANE_DEBUGGER_PORT", options, default=5678
        )
        self.merge_option(
            "webhook_url", "HURRICANE_WEBHOOK_URL", options, optional=True
        )
        self.merge_option(
            "max_lifetime",
            "HURRICANE_MAX_LIFETIME",
            options,
            optional=True,
            default=None,
        )
        self.merge_option(
            "max_memory", "HURRICANE_MAX_MEMORY", options, optional=True, default=None
        )
        self.merge_option(
            "workers", "HURRICANE_WORKERS", options, optional=True, default=None
        )
        self.merge_option(
            "static_watch", "HURRICANE_STATIC_WATCH", options, optional=True
        )
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

    def handle(self, *args, **options):
        """
        Defines functionalities for different arguments. After all arguments were processed, it starts the async event
        loop.
        """
        self.merge_options(options)
        start_time = time.time()
        if STRUCTLOG_ENABLED:
            logger.info(
                "Tornado-powered Django web server.",
                hurricane=HURRICANE_DIST_VERSION,
            )
        else:
            logger.info(
                f"Tornado-powered Django web server. Version: {HURRICANE_DIST_VERSION}"
            )

        if options["autoreload"]:
            tornado.autoreload.start()
            if options["static_watch"] and len(options["static_watch"]):
                logger.info("Watching static files for any changes")
                for path in options["static_watch"]:
                    if os.path.exists(path):
                        logger.info("Watching path {}.".format(path))
                        tornado.autoreload.watch(path)
                    else:
                        logger.error(
                            "Tried to watch {}, but it does not exist.".format(path)
                        )
                tornado.autoreload.add_reload_hook(static_watch)
            logger.info("Autoreload was performed")

        # set the probe port
        # the probe port by default is supposed to run the next port of the application
        probe_port = (
            options["probe_port"] if options["probe_port"] else options["port"] + 1
        )
        options["probe_port"] = probe_port

        # sanitize probes: returns regexps for probes in options and their representations for logging
        options, probe_representations = sanitize_probes(options)

        # set the probe routes
        # if probe port is set to the application's port, add it to the application's routes
        include_probe = False
        if not options["no_probe"]:
            if probe_port != options["port"]:
                if STRUCTLOG_ENABLED:
                    self.structlog_probe_configured(
                        probe_port, probe_representations, options
                    )
                else:
                    logger.info(
                        f"Starting probe application running on port {probe_port} with route liveness-probe: "
                        f"{probe_representations['liveness_probe']}, "
                        f"readiness-probe: {probe_representations['readiness_probe']}, "
                        f"startup-probe: {probe_representations['startup_probe']}"
                    )
                self.log_prometheus(options, probe_port)
                probe_application = make_probe_server(options, self.check)
                probe_application.listen(probe_port)
            else:
                include_probe = True
                if STRUCTLOG_ENABLED:
                    self.structlog_probe_configured(
                        probe_port, probe_representations, options
                    )
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
                logger.info(
                    "Running without Prometheus exporter, because --no-probe flag was set"
                )
            options["no_metrics"] = True

        setup_debugging(options)

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
        if options["check_migrations"] or options["check_migrations_apply"]:
            check_db_and_migrations_wrapper = functools.partial(
                check_db_and_migrations,
                webhook_url=options["webhook_url"] or None,
                loop=loop,
                apply_migration=True if options["check_migrations_apply"] else False,
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
        loop.run_in_executor(
            executor, bundle_func, exec_list, loop, make_http_server_wrapper
        )
        if options["max_memory"]:
            if STRUCTLOG_ENABLED:
                logger.info(
                    "Memory allocation check",
                    max_memory_mb=options["max_memory"],
                    active=True,
                )
            else:
                logger.info(
                    f"Starting memory allocation check with maximum memory set to {options['max_memory']} Mb"
                )
            loop.create_task(check_mem_allocations(options["max_memory"]))
        else:
            if STRUCTLOG_ENABLED:
                logger.warning("Memory allocation check", active=False)
            else:
                logger.warning("Starting without memory allocation check")

        def ask_exit(signame):
            logger.info(f"Received signal {signame}. Shutting down now.")
            loop.stop()

        for signame in ("SIGINT", "SIGTERM"):
            loop.add_signal_handler(
                getattr(signal, signame), functools.partial(ask_exit, signame)
            )

        loop.run_forever()

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
                    f"Starting Prometheus metrics exporter on port {probe_port} with "
                    f"route {options['metrics_path']}"
                )
        else:
            if STRUCTLOG_ENABLED:
                logger.info(PROMETHEUS_CONFIGURED_EVENT, active=False)
            else:
                logger.info(
                    "Running without Prometheus exporter, because --no-metrics flag was set"
                )
