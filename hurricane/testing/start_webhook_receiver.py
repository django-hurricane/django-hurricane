try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from hurricane.testing.actors import WebhookReceiverServer


def start_receiver():
    logger.info("Started webhook receiver server")
    server = WebhookReceiverServer().make_http_receiver_server(8074)
    server.serve_forever()


if __name__ == "__main__":
    start_receiver()
