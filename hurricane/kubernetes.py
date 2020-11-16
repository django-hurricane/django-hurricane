import asyncio

import tornado.web

from .server import metrics_log

logger = metrics_log


class K8sServerMetricsHandler(tornado.web.RequestHandler):
    """ This handler reports current usage statistics to Kubernetes """

    def get(self):
        # write custom metrics to MetricsAPI in the future
        request_queue_length = len(asyncio.all_tasks())
        logger.info(f"Request count: {request_queue_length}")
        self.write(request_queue_length)
