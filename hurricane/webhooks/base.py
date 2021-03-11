import asyncio
import functools
import traceback
from concurrent.futures.thread import ThreadPoolExecutor
from enum import Enum

import requests

from hurricane.server.loggers import logger


class WebhookStatus(Enum):
    FAILED = "failed"
    SUCCEEDED = "succeeded"


class Webhook:
    """
    Base class for webhooks in the registry. Run function initiates sending of webhook to the specified url.
    """

    code = None
    data = {}

    def __init__(self, code=None):
        if code:
            self.code = code

    @classmethod
    def get_from_registry(cls):

        """
        Getting metric from registry using metric code.
        """

        from hurricane.metrics import registry

        return registry.get(cls.code)

    def run(self, url: str, status: WebhookStatus, error_trace: str = None, close_loop: bool = False):
        if error_trace:
            self.set_traceback(error_trace)
        self.set_status(status)

        current_loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        fut = current_loop.run_in_executor(executor, self._send_webhook, self.get_message(), url)
        # callback runs after run_in_executor is done
        callback_wrapper = functools.partial(self._callback_webhook_exception_check, url=url, close_loop=close_loop)
        fut.add_done_callback(callback_wrapper)

    def _send_webhook(self, data: dict, webhook_url: str):
        # sending webhook request to the specified url
        logger.info(f"Start sending {self.code} to {webhook_url}")
        # TODO: catch exceptions
        response = requests.post(webhook_url, timeout=5, data=data)
        if response.status_code != 200:
            logger.warning(
                f"Request to the webhook endpoint " f"returned an error:\n {response.status_code} {response.text}"
            )
        logger.info(f"{self.code} has been sent")

    def set_traceback(self, traceback: str):
        self.data["traceback"] = traceback

    def set_status(self, status: WebhookStatus):
        self.data["status"] = status.value

    def get_message(self):
        return self.data

    @staticmethod
    def _callback_webhook_exception_check(future: asyncio.Future, url: str, close_loop: bool):
        # checks if sending webhook had any failures, it indicates, that command was successfully executed
        # but sending webhook has failed
        try:
            future.result()
        except Exception as e:
            logger.error(f"Sending webhook to {url} has failed")
            logger.error(e)
            logger.error(traceback.print_exc())
            if close_loop:
                current_loop = asyncio.get_event_loop()
                current_loop.stop()
