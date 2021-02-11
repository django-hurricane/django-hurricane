import tornado.web
from django.conf import settings
from django.core.management.base import SystemCheckError
from django.core.wsgi import get_wsgi_application
from django.db import OperationalError, connection

from hurricane.metrics import RequestQueueLengthMetric, ResponseTimeAverageMetric
from hurricane.server.wsgi import HurricaneWSGIContainer


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

    def prepare(self) -> None:
        """
        Transmitting incoming request to django application via WSGI Container.
        """
        self.django(self.request)
        self._finished = True
        self._log()
        self.on_finish()


class DjangoCheckHandler(tornado.web.RequestHandler):

    """
    This handler runs with every call to the probe endpoint, which is supposed to be used
    with Kubernetes 'Liveness Probes'. The DjangoCheckHandler calls Django's Check Framework which
    can be used to determine the application's health state during its operation.
    """

    def initialize(self, check_handler):
        """
        Initialization of check handler.
        """
        self.check = check_handler

    def compute_etag(self):
        return None

    def _check(self):
        """
        Checking application on several errors. Catches SystemCheckErrors of django system check framework and
        checks the connection to the database.
        """
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
        """
        Setting of extra headers for cache-control, namely: no-store, no-cache, must-revalidate and max-age=0. It
        means that information on requests and responses will not be stored.
        """
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")

    def get(self):
        """
        Get method, which runs the check.
        """
        self._check()

    def post(self):
        """
        Post method, which runs the check.
        """
        self._check()
