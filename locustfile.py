import logging

from locust import HttpUser, between, events, task
from locust.contrib.fasthttp import FastHttpUser


class WebsiteUser(FastHttpUser):
    wait_time = between(5, 15)

    @task
    def admin(self):
        self.client.get("/")


@events.quitting.add_listener
def _(environment, **kw):
    logging.info(f"Average response time: {environment.stats.total.avg_response_time}")
    logging.info(f"95th percentile response time: {environment.stats.total.get_response_time_percentile(0.95)}")
    if environment.stats.total.fail_ratio > 0.01:
        logging.error("Test failed due to failure ratio > 1%")
        environment.process_exit_code = 1
    elif environment.stats.total.avg_response_time > 6:
        logging.error("Test failed due to average response time ratio > 3 ms")
        environment.process_exit_code = 1
    elif environment.stats.total.get_response_time_percentile(0.95) > 6:
        logging.error("Test failed due to 95th percentile response time > 2 ms")
        environment.process_exit_code = 1
    else:
        environment.process_exit_code = 0
