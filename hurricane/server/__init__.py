import tornado
from django.conf import settings

from hurricane.metrics import RequestCounterMetric, ResponseTimeAverageMetric
from hurricane.server.django import DjangoCheckHandler, DjangoHandler
from hurricane.server.loggers import access_log, logger


class HurricaneApplication(tornado.web.Application):
    def __init__(self, *args, **kwargs):
        self.collect_metrics = True
        if "metrics" in kwargs:
            self.collect_metrics = kwargs["metrics"]
        super(HurricaneApplication, self).__init__(*args, **kwargs)

    def log_request(self, handler: DjangoHandler) -> None:
        """Writes a completed HTTP request to the logs. """
        if handler.get_status() < 400:
            log_method = access_log.info
        elif handler.get_status() < 500:
            log_method = access_log.warning
        else:
            log_method = access_log.error
        request_time = 1000.0 * handler.request.request_time()
        log_method(
            "%d %s %.2fms",
            handler.get_status(),
            handler._request_summary(),
            request_time,
        )
        if self.collect_metrics:
            RequestCounterMetric.increment()
            ResponseTimeAverageMetric.add_value(request_time)


def make_probe_server(options, check_func):
    """ create probe route application """
    handlers = [(options["probe"], DjangoCheckHandler, {"check_handler": check_func})]
    return HurricaneApplication(handlers, debug=options["debug"], metrics=False)


def make_http_server(options, check_func, include_probe=False):
    """ create all routes for this application """
    if include_probe:
        handlers = [(options["probe"], DjangoCheckHandler, {"check_handler": check_func})]
    else:
        handlers = []
    # if static file serving is enabled
    if options["static"]:
        logger.info(f"Serving static files under {settings.STATIC_URL} from {settings.STATIC_ROOT}")
        handlers.append(
            (
                f"{settings.STATIC_URL}(.*)",
                tornado.web.StaticFileHandler,
                {"path": settings.STATIC_ROOT},
            )
        )
    # if media file serving is enabled
    if options["media"]:
        logger.info(f"Serving media files under {settings.MEDIA_URL} from {settings.MEDIA_ROOT}")
        handlers.append(
            (
                f"{settings.MEDIA_URL}(.*)",
                tornado.web.StaticFileHandler,
                {"path": settings.MEDIA_ROOT},
            )
        )

    # append the django routing system
    handlers.append((".*", DjangoHandler))
    return HurricaneApplication(handlers, debug=options["debug"], metrics=not options["no_metrics"])
