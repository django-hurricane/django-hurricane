import asyncio
import functools
import os
import signal
import sys
import time

import tornado.autoreload
import tornado.ioloop
import tornado.web
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.module_loading import import_string

from hurricane.amqp import logger
from hurricane.amqp.basehandler import _AMQPConsumer
from hurricane.amqp.worker import AMQPClient
from hurricane.metrics import StartupTimeMetric
from hurricane.server import make_probe_server, sanitize_probes


class Command(BaseCommand):

    """
    Starting a Tornado-powered Django AMQP 0-9-1 consumer.
    Implements consume command as a management command for django application.
    The new command can be called using ``python manage.py consume <arguments>``.
    Arguments:
        - ``--queue`` - the AMQP 0-9-1 queue to consume from
        - ``--exchange`` - the AMQP 0-9-1 exchange to declare
        - ``--amqp-port`` - the message broker connection port
        - ``--amqp-host`` - the host address of the message broker
        - ``--amqp-vhost`` - the virtual host of the message broker to use with this consumer
        - ``--handler`` - the Hurricane AMQP handler class (dotted path)
        - ``--startup-probe`` - the exposed path (default is /startup) for probes to check startup
        - ``--readiness-probe`` - the exposed path (default is /ready) for probes to check readiness
        - ``--liveness-probe`` - the exposed path (default is /alive) for probes to check liveness
        - ``--probe-port`` - the port for Tornado probe route to listen on
        - ``--req-queue-len`` - threshold of length of queue of request, which is considered for readiness probe
        - ``--no-probe`` - disable probe endpoint
        - ``--no-metrics`` - disable metrics collection
        - ``--autoreload`` - reload code on change
        - ``--debug`` - set Tornado's Debug flag
        - ``--reconnect`` - try to reconnect this client automatically as the broker is available again
        - ``--max-lifetime``- If specified,  maximum requests after which pod is restarted
    """

    help = "Start a Tornado-powered Django AMQP 0-9-1 consumer"

    def add_arguments(self, parser):

        """
        Defines arguments, that can be accepted with ``consume`` command.
        """

        parser.add_argument("--queue", type=str, default="", help="The AMQP 0-9-1 queue to consume from")
        parser.add_argument("--exchange", type=str, default="", help="The AMQP 0-9-1 exchange to declare")
        parser.add_argument(
            "--amqp-port",
            type=int,
            help="The message broker connection port",
        )
        parser.add_argument(
            "--amqp-host",
            type=str,
            help="The host address of the message broker",
        )
        parser.add_argument(
            "--amqp-vhost",
            type=str,
            help="The virtual host of the message broker to use with this consumer",
        )
        parser.add_argument("handler", type=str, help="The Hurricane AMQP handler class (dotted path)")
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
            default=8001,
            help="The port for Tornado probe route to listen on",
        )
        parser.add_argument("--req-queue-len", type=int, default=10, help="Length of the request queue")
        parser.add_argument("--no-probe", action="store_true", help="Disable probe endpoint")
        parser.add_argument("--no-metrics", action="store_true", help="Disable metrics collection")
        parser.add_argument("--autoreload", action="store_true", help="Reload code on change")
        parser.add_argument("--debug", action="store_true", help="Set Tornado's Debug flag")
        parser.add_argument(
            "--reconnect",
            action="store_true",
            help="Try to reconnect this client automatically as the broker is available again",
        )
        parser.add_argument(
            "--webhook-url",
            type=str,
            help="Url for webhooks",
        )
        parser.add_argument(
            "--max-lifetime", type=int, default=None, help="Maximum requests after which pod is restarted"
        )

    def handle(self, *args, **options):

        """
        Defines functionalities for different arguments. After all arguments were processed, it starts the async event
        loop.
        """
        start_time = time.time()
        logger.info("Starting a Tornado-powered Django AMQP consumer")

        if options["autoreload"]:
            tornado.autoreload.start()
            logger.info("Autoreload was performed")

        # sanitize probes: returns regexps for probes in options and their representations for logging
        options, probe_representations = sanitize_probes(options)

        # set the probe routes
        if not options["no_probe"]:
            logger.info(f"Probe application running on port {options['probe_port']}")
            probe_application = make_probe_server(options, self.check)
            probe_application.listen(options["probe_port"])
        else:
            logger.info("No probe application running")

        connection = self.set_connection_values(options)

        # load the handler class
        _amqp_consumer = import_string(options["handler"])
        if not issubclass(_amqp_consumer, _AMQPConsumer):
            logger.error(f"The type {_amqp_consumer} is not subclass of _AMQPConsumer")
            raise CommandError("Cannot start the consumer due to an implementation error")

        worker = AMQPClient(
            _amqp_consumer,
            queue_name=options["queue"],
            exchange_name=options["exchange"],
            amqp_host=connection["amqp_host"],
            amqp_port=connection["amqp_port"],
            amqp_vhost=connection["amqp_vhost"],
        )

        # prepate the io loop
        loop = asyncio.get_event_loop()

        def ask_exit(signame):
            logger.info(f"Received signal {signame}. Shutting down now.")
            loop.stop()
            sys.exit(0)

        for signame in ("SIGINT", "SIGTERM"):
            loop.add_signal_handler(getattr(signal, signame), functools.partial(ask_exit, signame))
        end_time = time.time()
        time_elapsed = end_time - start_time
        StartupTimeMetric.set(time_elapsed)
        worker.run(options["reconnect"])

    def set_connection_values(self, options):
        # load connection data
        connection = {}
        if "amqp_host" in options and options["amqp_host"]:
            connection["amqp_host"] = options["amqp_host"]
        elif hasattr(settings, "AMQP_HOST"):
            connection["amqp_host"] = settings.AMQP_HOST
        elif os.getenv("AMQP_HOST"):
            connection["amqp_host"] = os.getenv("AMQP_HOST")
        else:
            raise CommandError(
                "The amqp host must not be empty: set it either as environment AMQP_HOST, "
                "in the django settings as AMQP_HOST or as optional argument --amqp-host"
            )
        if "amqp_port" in options and options["amqp_port"]:
            connection["amqp_port"] = options["amqp_port"]
        elif hasattr(settings, "AMQP_PORT"):
            connection["amqp_port"] = settings.AMQP_PORT
        elif os.getenv("AMQP_PORT"):
            connection["amqp_port"] = int(os.getenv("AMQP_PORT"))
        else:
            raise CommandError(
                "The amqp port must not be empty: set it either as environment AMQP_PORT, "
                "in the django settings as AMQP_PORT or as optional argument --amqp-port"
            )
        connection["amqp_vhost"] = "/"
        if "amqp_vhost" in options and options["amqp_vhost"]:
            connection["amqp_vhost"] = options["amqp_vhost"]
        elif hasattr(settings, "AMQP_VHOST"):
            connection["amqp_vhost"] = settings.AMQP_VHOST
        elif os.getenv("AMQP_VHOST"):
            connection["amqp_vhost"] = os.getenv("AMQP_VHOST")

        return connection
