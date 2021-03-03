import logging

import tornado.ioloop

from hurricane.testing.actors import WebhookReceiverServer

if __name__ == "__main__":
    logging.basicConfig(filename="webhook", level="INFO")
    logging.info("Started webhook server")
    app = WebhookReceiverServer().make_http_receiver_app()
    app.listen(8074)
    tornado.ioloop.IOLoop.current().start()
