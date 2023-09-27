try:
    import structlog

    logger = structlog.get_logger("hurricane.amqp.general")
    metrics_log = structlog.get_logger("hurricane.amqp.metrics")
except ImportError:
    import logging

    logger = logging.getLogger("hurricane.amqp.general")
    metrics_log = logging.getLogger("hurricane.amqp.metrics")
