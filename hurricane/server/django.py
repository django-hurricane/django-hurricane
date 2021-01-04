import tornado.web
from django.conf import settings
from django.core.management.base import SystemCheckError
from django.core.wsgi import get_wsgi_application
from django.db import OperationalError, connection

from hurricane.metrics import RequestQueueLengthMetric, ResponseTimeAverageMetric
from hurricane.server.wsgi import HurricaneWSGIContainer


class DjangoHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.django = HurricaneWSGIContainer(self, get_wsgi_application())

    def prepare(self) -> None:
        self.django(self.request)
        self._finished = True
        self._log()
        self.on_finish()


class DjangoCheckHandler(tornado.web.RequestHandler):
    """
    This handler runs with ever call to the probe endpoint which is supposed to be used
    with Kubernetes 'Liveness Probes'. The DjangoCheckHandler calls Django's Check Framework which
    can be used to determine the application's health state during its operation.
    """

    def initialize(self, check_handler):
        self.check = check_handler

    def compute_etag(self):
        return None

    def _check(self):
        try:
            self.check()
            if settings.DATABASES:
                # once a connection has been established, this will be successful
                # (even if the connection is gone later on)
                connection.ensure_connection()
        except SystemCheckError as e:
            if settings.DEBUG:
                self.write("django check error: " + str(e))
            else:
                self.write("check error")
            self.set_status(500)
        except OperationalError as e:
            if settings.DEBUG:
                self.write("django database error: " + str(e))
            else:
                self.write("db error")
            self.set_status(500)
        else:
            if response_average_time := ResponseTimeAverageMetric.get():
                self.write(
                    f"Average response time: {response_average_time:.2f}ms Request "
                    f"queue size: {RequestQueueLengthMetric.get()} Rx"
                )
            else:
                self.write("alive")

    def set_extra_headers(self, path):
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")

    def get(self):
        self._check()

    def post(self):
        self._check()
