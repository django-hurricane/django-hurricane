try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

import tornado.ioloop

from hurricane.testing.actors import WebhookReceiverServer


def start_receiver():
    logger.info("Started webhook receiver server")
    app = WebhookReceiverServer().make_http_receiver_app()
    app.listen(8074)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    start_receiver()
