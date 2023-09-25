try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

import tornado.ioloop

from hurricane.testing.actors import K8sServer


def start_server():
    logging.info("Started K8s server")
    app = K8sServer().make_http_receiver_app()
    app.listen(8072)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    start_server()
