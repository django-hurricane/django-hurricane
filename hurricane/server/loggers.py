try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

access_log = logging.getLogger("hurricane.server.access")
app_log = logging.getLogger("hurricane.server.application")
logger = logging.getLogger("hurricane.server.general")
metrics_log = logging.getLogger("hurricane.server.metrics")
