try:
    import structlog

    access_log = structlog.get_logger("hurricane.server.access")
    app_log = structlog.get_logger("hurricane.server.application")
    logger = structlog.get_logger("hurricane.server.general")
    metrics_log = structlog.get_logger("hurricane.server.metrics")
    STRUCTLOG_ENABLED = True
except ImportError:
    import logging

    access_log = logging.getLogger("hurricane.server.access")
    app_log = logging.getLogger("hurricane.server.application")
    logger = logging.getLogger("hurricane.server.general")
    metrics_log = logging.getLogger("hurricane.server.metrics")
    STRUCTLOG_ENABLED = False
