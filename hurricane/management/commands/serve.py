import asyncio
import functools
import signal

import tornado.autoreload
import tornado.web
import tornado.wsgi
from django.core.management.base import BaseCommand
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
            "--probe",
            type=str,
            default="/alive",
            help="The exposed path (default is /alive) for probes to check liveness and readyness",
        )
        parser.add_argument(
            "--probe-port",
            type=int,
            help="The port for Tornado probe route to listen on",
        )
        parser.add_argument("--no-probe", action="store_true", help="Disable probe endpoint")
        parser.add_argument("--no-metrics", action="store_true", help="Disable metrics collection")

    def handle(self, *args, **options):
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
        if options["probe"][0] != "/":
            options["probe"] = "/" + options["probe"]

        # set the probe routes
        # if the probe port is set to the application's port, include it to the application's routes
        include_probe = False
        if not options["no_probe"]:
            if probe_port != options["port"]:
                logger.info(f"Probe application running on port {probe_port} with route {options['probe']}")
                probe_application = make_probe_server(options, self.check)
                probe_application.listen(probe_port)
            else:
                include_probe = True
                logger.info(f"Probe application with route {options['probe']} running integrated on port {probe_port}")
        else:
            logger.info("No probe application running")

        django_application = make_http_server(options, self.check, include_probe)
        django_application.listen(options["port"])

        # prepate the io loop
        loop = asyncio.get_event_loop()

        def ask_exit(signame):
            logger.info(f"Received signal {signame}. Shutting down now.")
            loop.stop()

        for signame in ("SIGINT", "SIGTERM"):
            loop.add_signal_handler(getattr(signal, signame), functools.partial(ask_exit, signame))

        loop.run_forever()
