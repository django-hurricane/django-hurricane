from typing import Any, Optional

from prometheus_client import Counter, Gauge, Histogram

CONTINUOUS_LOOP_TASKS = 5  # 5 is the number of tasks that are always running


class StoredMetric:
    """
    Base class for storing metrics in registry.
    """

    code: str = ""
    value: Optional[Any] = None

    def __init__(self, code=None, initial=None):
        if code:
            self.code = code
        if initial:
            self.value = initial

    @classmethod
    def get_from_registry(cls):
        """
        Getting metric from registry using metric code.
        """

        from hurricane.metrics import registry

        return registry.get(cls.code)

    @classmethod
    def set(cls, value):
        """
        Setting new value for metric.
        """

        metric = cls.get_from_registry()
        metric.value = value

    @classmethod
    def get(cls):
        """
        Getting value of metric from registry.
        """

        metric = cls.get_from_registry()
        return metric.value


class CalculatedMetric:
    code: str = ""

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

    @classmethod
    def get(cls):
        """
        Getting value of metric from registry.
        """

        return cls.get_value(cls)

    @classmethod
    def get_value(cls):
        raise NotImplementedError


class CounterMetric(StoredMetric):

    """
    Metric, that can be incremented and decremented.
    """

    code: str = ""
    value = 0
    prometheus: Optional[Counter] = None

    @classmethod
    def increment(cls):
        """
        Increment value to the metric.
        """
        if cls.prometheus:
            cls.prometheus.inc()
        cls.set(cls.get() + 1)

    @classmethod
    def decrement(cls):
        """
        Decrement value from the metric.
        """
        # not supported: cls.prometheus.dec()
        cls.set(cls.get() - 1)


class AverageMetric(StoredMetric):

    """
    Calculating average of a metric.
    """

    counter = 0
    value = 0
    prometheus: Optional[Gauge] = None

    @classmethod
    def add_value(cls, value):
        """
        Implements the running (online) average of a metric.
        """

        metric = cls.get_from_registry()
        metric.counter += 1
        metric.value = metric.value + (value - metric.value) / metric.counter
        if cls.prometheus:
            cls.prometheus.set(metric.value)


class ObservedMetric(StoredMetric):

    """
    Metric, that can be oberserved.
    """

    code: str = ""
    value = 0
    prometheus: Optional[Histogram] = None

    @classmethod
    def observe(cls, value):
        if cls.prometheus:
            cls.prometheus.observe(value)
        cls.set(value)
