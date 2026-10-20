"""
Django request and probe handlers for Hurricane.
"""

from typing import Any, Callable, Optional

from hurricane.server.gateway import HurricaneWSGIGateway


class DjangoHandler:
    """
    Transmits standard HTTP requests to the Django application.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass


class DjangoStaticFilesHandler(DjangoHandler):
    """
    Transmits static file requests to the Django application or static handler.
    """

    pass


class DjangoProbeHandler:
    """
    Base handler for Kubernetes probes.
    """

    pass


class DjangoLivenessHandler(DjangoProbeHandler):
    """
    Handler for Kubernetes Liveness probes (/alive).
    """

    pass


class DjangoReadinessHandler(DjangoProbeHandler):
    """
    Handler for Kubernetes Readiness probes (/ready).
    """

    pass


class DjangoStartupHandler(DjangoProbeHandler):
    """
    Handler for Kubernetes Startup probes (/startup).
    """

    pass


class PrometheusHandler:
    """
    Handler for Prometheus metrics exposition (/metrics).
    """

    pass
