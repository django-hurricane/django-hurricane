try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

logger = logging.getLogger("hurricane.amqp.general")
metrics_log = logging.getLogger("hurricane.amqp.metrics")
