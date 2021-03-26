import asyncio
import functools
import socket
import time
import traceback
from concurrent.futures.thread import ThreadPoolExecutor
from enum import Enum

import requests
from django.conf import settings
from requests import HTTPError, RequestException

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
        Getting webhook from registry using the code.
        """

        from hurricane.metrics import registry

        return registry.get(cls.code)

    def run(self, url: str, status: WebhookStatus, error_trace: str = None, close_loop: bool = False):

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

        self.set_traceback(error_trace)
        self.set_status(status)
        self.set_timestamp()
        self.set_hostname()
        self.set_version()
        current_loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        fut = current_loop.run_in_executor(executor, self._send_webhook, self.get_message(), url)
        # callback runs after run_in_executor is done
        callback_wrapper = functools.partial(self._callback_webhook_exception_check, url=url, close_loop=close_loop)
        fut.add_done_callback(callback_wrapper)

    def _send_webhook(self, data: dict, webhook_url: str):
        # sending webhook request to the specified url
        logger.info(f"Start sending {self.code} webhook to {webhook_url}")

        try:
            response = requests.post(webhook_url, timeout=5, json=data)
            response.raise_for_status()
            logger.info(f"{self.code} webhook has been sent successfully")
        except HTTPError:
            logger.warning(
                f"{self.code} webhook request to endpoint returned an error:\n {response.status_code} {response.text}"
            )
        except RequestException as e:
            logger.warning(f"{self.code} could not send webhook request: {e}")

    def set_traceback(self, traceback: str):
        self.data["traceback"] = traceback

    def set_timestamp(self):
        self.data["timestamp"] = int(time.time())

    def set_hostname(self):
        self.data["hostname"] = socket.gethostname()

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
                logger.info("Loop will be closed")
                current_loop = asyncio.get_event_loop()
                current_loop.stop()
