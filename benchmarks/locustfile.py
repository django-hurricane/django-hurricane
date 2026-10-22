import time

from locust import FastHttpUser, between, constant, task


class StandardTrafficUser(FastHttpUser):
    """
    Simulates standard user browsing with realistic think time.
    """

    wait_time = between(0.5, 2.0)
    weight = 5

    @task(5)
    def index(self):
        self.client.get("/")

    @task(3)
    def medium(self):
        self.client.get("/medium")

    @task(1)
    def heavy(self):
        self.client.get("/heavy")


class HighLoadUser(FastHttpUser):
    """
    Simulates burst traffic / saturation with zero think time.
    """

    wait_time = constant(0)
    weight = 10

    @task(5)
    def index(self):
        self.client.get("/")

    @task(3)
    def medium(self):
        self.client.get("/medium")


class ProbeObserverUser(FastHttpUser):
    """
    Simulates Kubernetes kubelet polling liveness and readiness probes.
    """

    wait_time = constant(0.5)
    weight = 1

    @task
    def check_liveness(self):
        with self.client.get("/alive", catch_response=True, timeout=3.0) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Liveness probe failed with status {resp.status_code}")

    @task
    def check_readiness(self):
        with self.client.get("/ready", catch_response=True, timeout=3.0) as resp:
            # Track both 200 (ready) and 400 (unready) as valid responses, but log status
            if resp.status_code in (200, 400):
                resp.success()
            else:
                resp.failure(f"Readiness probe failed unexpectedly with status {resp.status_code}")
