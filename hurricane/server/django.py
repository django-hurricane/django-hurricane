import traceback

import tornado.web
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.management.base import SystemCheckError
from django.core.wsgi import get_wsgi_application
from django.db import OperationalError, connection

from hurricane.metrics import (
    HealthMetric,
    ReadinessMetric,
    RequestCounterMetric,
    RequestQueueLengthMetric,
    ResponseTimeAverageMetric,
    StartupTimeMetric,
)
from hurricane.server.loggers import logger
from hurricane.server.wsgi import HurricaneWSGIContainer
from hurricane.webhooks import LivenessWebhook, ReadinessWebhook
from hurricane.webhooks.base import WebhookStatus


class DjangoHandler(tornado.web.RequestHandler):

    """
    This handler transmits all standard requests to django application. Currently it uses WSGI Container based on
    tornado WSGI Container.
    """

    def initialize(self):
        """
        Initialization of Hurricane WSGI Container.
        """
        self.django = HurricaneWSGIContainer(self, get_wsgi_application())

    async def prepare(self) -> None:
        """
        Transmitting incoming request to django application via WSGI Container.
        """
        await self.django(self.request)
        self._finished = True
        self._log()
        self.on_finish()


class DjangoProbeHandler(tornado.web.RequestHandler):

    """
    Parent class for all specific probe handlers.
    """

    def compute_etag(self):
        return None

    def set_extra_headers(self, path):
        """
        Setting of extra headers for cache-control, namely: no-store, no-cache, must-revalidate and max-age=0. It
        means that information on requests and responses will not be stored.
        """
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")

    async def _check(self):
        """
        Checking application on several errors. Catches SystemCheckErrors of django system check framework and
        checks the connection to the database.
        """
        pass

    async def _check_startup_wrapper(self):
        """
        Checking application on several errors. Catches SystemCheckErrors of django system check framework and
        checks the connection to the database.
        """
        if StartupTimeMetric.get():
            await self._check()
        else:
            self.set_status(400)

    def _probe_check(self):
        """
        Checking application on several errors. Catches SystemCheckErrors of django system check framework and
        checks the connection to the database.
        """
        pass

    async def get(self):
        """
        Get method, which runs the check.
        """
        await self._check_startup_wrapper()

    async def post(self):
        """
        Post method, which runs the check.
        """
        await self._check_startup_wrapper()

    @sync_to_async
    def _ensure_connection(self):
        connection.ensure_connection()

    async def _custom_check_wrapper(self, tag, metric, webhook, webhook_url):
        got_exception = None
        try:
            async_check = sync_to_async(self.check)
            await async_check(tags=[tag], include_deployment_checks=True)
            if settings.DATABASES:
                # once a connection has been established, this will be successful
                # (even if the connection is gone later on)
                await self._ensure_connection()
        except SystemCheckError as e:
            got_exception = traceback.format_exc()
            self._write_error(msg="check error", e=e)
        except OperationalError as e:
            got_exception = traceback.format_exc()
            self._write_error(msg="database error", e=e)
        else:
            self._probe_check()
            self._update_health_metric_no_exception(metric, webhook, webhook_url)
        finally:
            if got_exception:
                self.set_status(500)
                self._update_health_metric_exception(metric, webhook, webhook_url)

    def _update_health_metric_no_exception(self, metric, webhook, webhook_url):
        if not metric.get():
            metric_change = True
            metric.set(metric_change)
            self._send_webhook(metric, webhook, webhook_url, WebhookStatus.SUCCEEDED, metric_change)

    def _update_health_metric_exception(self, metric, webhook, webhook_url):
        if metric.get() or metric.get() is None:
            metric_change = False
            metric.set(metric_change)
            self._send_webhook(metric, webhook, webhook_url, WebhookStatus.FAILED, metric_change)

    def _write_error(self, msg, e=None):
        if settings.DEBUG:
            self.write(f"django {msg}: " + str(e))
        else:
            self.write(f"{msg}")

    def _send_webhook(self, metric, webhook, webhook_url, status, metric_change):
        if webhook_url:
            logger.info(
                f"{metric.code.capitalize()} metric changed to {metric_change}. {webhook.code.capitalize()} webhook with status {status} triggered"
            )
            webhook().run(url=webhook_url, status=status)


class DjangoLivenessHandler(DjangoProbeHandler):
    """
    This handler runs with every call to the probe endpoint which is supposed to be used
    """

    def initialize(self, check_handler, webhook_url, max_lifetime):
        self.check = check_handler
        self.liveness_webhook_url = webhook_url
        self.liveness_webhook = LivenessWebhook
        self.metric = HealthMetric
        self.tag = "liveness"
        self.max_lifetime = max_lifetime

    async def _check(self):
        await self._custom_check_wrapper(self.tag, self.metric, self.liveness_webhook, self.liveness_webhook_url)

    def _probe_check(self):
        if self.max_lifetime and RequestCounterMetric.get() > self.max_lifetime:
            self.set_status(400)
            return None
        if response_average_time := ResponseTimeAverageMetric.get():
            self.write(
                f"Average response time: {response_average_time:.2f}ms Request "
                f"queue size: {RequestQueueLengthMetric.get()} Rx"
            )
        else:
            self.write("alive")


class DjangoReadinessHandler(DjangoProbeHandler):
    """
    This handler runs with every call to the probe endpoint which is supposed to be used
    with Kubernetes 'Readiness Probes'. The DjangoCheckHandler calls Django's Check Framework which
    can be used to determine the application's health state during its operation.
    """

    def initialize(self, check_handler, req_queue_len, webhook_url):
        self.check = check_handler
        self.request_queue_length = req_queue_len
        self.readiness_webhook_url = webhook_url
        self.readiness_webhook = ReadinessWebhook
        self.metric = ReadinessMetric
        self.tag = "readiness"

    async def _check(self):
        await self._custom_check_wrapper(self.tag, self.metric, self.readiness_webhook, self.readiness_webhook_url)

    def _probe_check(self):
        if RequestQueueLengthMetric.get() > self.request_queue_length:
            self.set_status(400)
            self._update_health_metric_exception(self.metric, self.readiness_webhook, self.readiness_webhook_url)
        elif RequestQueueLengthMetric.get() <= self.request_queue_length:
            self.set_status(200)
            self._update_health_metric_no_exception(self.metric, self.readiness_webhook, self.readiness_webhook_url)


class DjangoStartupHandler(DjangoProbeHandler):
    """
    This handler runs with every call to the probe endpoint which is supposed to be used with Kubernetes
    'Startup Probes'. It returns 400 response for post and get requests, if StartupTimeMetric is not set, what means
    that the application is still in the startup phase. As soon as StartupTimeMetric is set, this handler returns 200
    response upon request, which indicates, that startup phase is finished and Kubernetes can now poll
    liveness/readiness probes.
    """

    async def _check(self):
        await self._probe_check()

    async def _probe_check(self):
        self.write(f"Startup was finished {StartupTimeMetric.get()}")
        self.set_status(200)
