import asyncio
import functools
import socket
import time
import typing
from concurrent.futures.thread import ThreadPoolExecutor
from enum import Enum

import requests
from django.conf import settings
from requests import RequestException

from hurricane.server.loggers import logger


class WebhookStatus(Enum):
    FAILED = "failed"
    SUCCEEDED = "succeeded"
    WARNING = "warning"


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
        Getting webhook from registry using the code.
        """

        from hurricane.webhooks import webhook_registry

        return webhook_registry.get(cls.code)

    def run(self, url: str, status: WebhookStatus, error_trace: str = None, close_loop: bool = False, loop=None):

        """
        Initiates the sending of webhook in an asynchronous manner. Also specifies the callback of the async process,
        which handles the feedback and either logs success or failure of a webhook sending process.

        Parameters
        ----------
        url : Url, which webhook should be sent to
        status : can be either WebhookStatus.FAILED or WebhookStatus.SUCCEEDED depending on the success or failure of
        the process, which should be indicated by the webhook
        error_trace : specifies the error trace of the preceding failure
        close_loop : specifies, whether the main loop should be closed or be left running
        """

        if url:
            self.set_traceback(error_trace)
            self.set_status(status)
            self.set_timestamp()
            self.set_podname()
            self.set_version()
            current_loop = loop or asyncio.get_event_loop()
            executor = ThreadPoolExecutor(max_workers=1)
            fut = current_loop.run_in_executor(executor, self._send_webhook, self.get_message(), url, close_loop)
            # callback runs after run_in_executor is done
            callback_wrapper = functools.partial(
                self._callback_webhook_exception_check, url=url, close_loop=close_loop, loop=loop
            )
            fut.add_done_callback(callback_wrapper)
        if not url and close_loop:
            logger.warning("No webhook can be sent, as no url is specified")
            self._callback_webhook_exception_check(future=None, url="", close_loop=True, loop=loop)

    def _send_webhook(self, data: dict, webhook_url: str, close_loop: bool):
        # sending webhook request to the specified url
        logger.info(f"Start sending {self.code} webhook to {webhook_url}")

        response = requests.post(webhook_url, timeout=5, json=data)
        response.raise_for_status()

    def set_traceback(self, error_trace: str):
        self.data["traceback"] = error_trace

    def set_timestamp(self):
        self.data["timestamp"] = int(time.time())

    def set_podname(self):
        self.data["podname"] = socket.gethostname()

    def set_status(self, status: WebhookStatus):
        self.data["status"] = status.value

    def set_version(self):
        if hasattr(settings, "HURRICANE_VERSION"):
            self.data["version"] = settings.HURRICANE_VERSION
        else:
            self.data["version"] = None

    def get_message(self):
        return self.data

    @staticmethod
    def _callback_webhook_exception_check(
        future: typing.Union[asyncio.Future, None], url: str, close_loop: bool, loop=None
    ):
        # checks if sending webhook had any failures, it indicates, that command was successfully executed
        # but sending webhook has failed
        if future:
            try:
                future.result()
            except RequestException as e:
                logger.warning(f"Sending webhook to {url} has failed due to {e}")

        if close_loop:
            logger.info("Loop will be closed")
            loop.stop()
