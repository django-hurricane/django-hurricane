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
from hurricane.metrics.shared import SharedMetrics


class RequestCounterMetric(CounterMetric):
    """
    Defines request counter metric with corresponding metric code.
    """

    code = "request_counter"
    prometheus = Counter(code, __doc__.strip())

    @classmethod
    def increment(cls):
        val = SharedMetrics.increment_requests()
        if cls.prometheus:
            cls.prometheus.inc()
        cls.value = val

    @classmethod
    def get(cls):
        val = SharedMetrics.get_requests()
        return val if val > 0 else (cls.value or 0)


class ResponseTimeAverageMetric(AverageMetric):
    """
    Defines response time average metric with corresponding metric code.
    """

    code = "response_time_average"
    prometheus = Gauge(code, __doc__.strip())
    value: Any = 0.0

    @classmethod
    def add_value(cls, value: float):
        avg = SharedMetrics.add_response_time(value)
        if cls.prometheus:
            cls.prometheus.set(avg)
        cls.value = avg

    @classmethod
    def get(cls):
        avg = SharedMetrics.get_average_response_time()
        return avg if avg > 0.0 else cls.value


class RequestQueueLengthMetric(CalculatedMetric):
    """
    Defines request queue length metric with corresponding metric code.
    """

    code = "request_queue_length"
    prometheus = Gauge(code, __doc__.strip())

    @classmethod
    def set(cls, value: int):
        SharedMetrics.set_queue_length(value)
        if cls.prometheus:
            cls.prometheus.set(value)

    @classmethod
    def get_value(cls, *args):
        return SharedMetrics.get_queue_length()


class StartupTimeMetric(StoredMetric):
    code = "startup_time"

    @classmethod
    def set(cls, value: Any):
        if value is None:
            SharedMetrics.set_startup_time(0.0)
            cls.value = None
        else:
            SharedMetrics.set_startup_time(float(value))
            cls.value = value

    @classmethod
    def get(cls):
        val = SharedMetrics.get_startup_time()
        return val if val is not None else cls.value


class HealthMetric(StoredMetric):
    code = "health"

    @classmethod
    def set(cls, value: Any):
        SharedMetrics.set_health(bool(value))
        cls.value = value

    @classmethod
    def get(cls):
        val = SharedMetrics.get_health()
        return val if val is not None else cls.value


class ReadinessMetric(StoredMetric):
    code = "readiness"

    @classmethod
    def set(cls, value: Any):
        SharedMetrics.set_readiness(bool(value))
        cls.value = value

    @classmethod
    def get(cls):
        val = SharedMetrics.get_readiness()
        return val if val is not None else cls.value


class ResponseTimeMetric(ObservedMetric):
    """
    Defines response time metric with corresponding metric code.
    """

    code = "response_time"
    prometheus = Histogram(code, __doc__.strip(), buckets=[0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10])


class ResponseSizeMetric(ObservedMetric):
    """
    Defines response size metric with corresponding metric code.
    """

    code = "response_size"
    prometheus = Histogram(
        code,
        __doc__.strip(),
        buckets=[100, 1000, 10000, 100000, 1000000, 10000000, 100000000],
    )


class PathCounterMetric(CounterMetric):
    """
    Defines response path metric with corresponding metric code.
    """

    code = "request_path"
    prometheus = Counter(code, __doc__.strip(), labelnames=["path"])


class InfoMetrics(CalculatedMetric):
    """
    Python package info of Hurricane
    """

    code = "hurricane"
    prometheus = Info(code, __doc__.strip())
    value: Any = None

    @classmethod
    def set(cls, value: Any):
        cls.prometheus.info(value)
        cls.value = value
