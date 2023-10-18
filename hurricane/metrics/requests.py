import asyncio
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, Info

from hurricane.metrics.base import (
    CONTINUOUS_LOOP_TASKS,
    AverageMetric,
    CalculatedMetric,
    CounterMetric,
    ObservedMetric,
    StoredMetric,
)


class RequestCounterMetric(CounterMetric):

    """
    Defines request counter metric with corresponding metric code.
    """

    code = "request_counter"
    prometheus = Counter(code, __doc__.strip())


class ResponseTimeAverageMetric(AverageMetric):

    """
    Defines response time average metric with corresponding metric code.
    """

    code = "response_time_average"
    prometheus = Gauge(code, __doc__.strip())


class RequestQueueLengthMetric(CalculatedMetric):

    """
    Defines request queue length metric with corresponding metric code.
    """

    code = "request_queue_length"
    prometheus = Gauge(code, __doc__.strip())

    def get_value(self):
        """
        Getting length of the asyncio queue of all tasks.
        """
        _len = max(0, len(asyncio.all_tasks()) - CONTINUOUS_LOOP_TASKS)
        self.prometheus.set(_len)
        return _len


class StartupTimeMetric(StoredMetric):
    code = "startup_time"


class HealthMetric(StoredMetric):
    code = "health"


class ReadinessMetric(StoredMetric):
    code = "readiness"


class ResponseTimeMetric(ObservedMetric):
    """
    The time to generate a response in seconds.
    """

    code = "response_time_seconds"
    prometheus = Histogram(code, __doc__.strip())


class ResponseSizeMetric(ObservedMetric):
    """
    The response size in bytes.
    """

    code = "response_size_bytes"
    prometheus = Histogram(code, __doc__.strip())


class PathCounterMetric(CounterMetric):
    """
    The number of requests to a specific path.
    """

    code = "path_requests_total"
    prometheus = Counter(code, __doc__.strip(), ["method", "path"])

    @classmethod
    def increment(cls, method, path):
        """
        Increment value to the metric.
        """
        if cls.prometheus:
            cls.prometheus.labels(method, path).inc()
        cls.set(cls.get() + 1)


class InfoMetrics(StoredMetric):
    """
    Python package info of Hurricane
    """

    code = "hurricane"
    prometheus = Info(code, __doc__.strip())

    @classmethod
    def set(cls, value: Any):
        cls.prometheus.info(value)
        cls.value = value
