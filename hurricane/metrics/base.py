import math
from typing import Any, Optional

from prometheus_client import Counter, Gauge, Histogram

CONTINUOUS_LOOP_TASKS = 5  # 5 is the number of tasks that are always running


class HurricaneMetric:
    """
    Base class for storing metrics in registry.
    """

    is_async: bool = False
    code: str = ""


class StoredMetric(HurricaneMetric):
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
    def _get_shared(cls):
        if not hasattr(cls, "_shared_storage"):
            import multiprocessing

            cls._shared_storage = multiprocessing.Value("d", 0.0)
        return cls._shared_storage

    @classmethod
    def set(cls, value):
        """
        Setting new value for metric in registry and shared memory.
        """

        metric = cls.get_from_registry()
        metric.value = value
        try:
            shared = cls._get_shared()
            with shared.get_lock():
                shared.value = float(value if value is not None else 0.0)
        except Exception:
            pass

    @classmethod
    def get(cls):
        """
        Getting value of metric from registry or shared memory.
        """

        metric = cls.get_from_registry()
        try:
            shared = cls._get_shared()
            with shared.get_lock():
                raw = shared.value
            if isinstance(metric.value, bool):
                return bool(raw)
            if isinstance(metric.value, int):
                return int(raw)
            if isinstance(metric.value, float):
                return raw
            if not math.isclose(raw, 0.0, abs_tol=1e-9):
                return raw
            return metric.value
        except Exception:
            return metric.value


class CalculatedMetric(HurricaneMetric):
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
    def _get_shared_counter(cls):
        if not hasattr(cls, "_shared_counter"):
            import multiprocessing

            cls._shared_counter = multiprocessing.Value("i", 0)
        return cls._shared_counter

    @classmethod
    def add_value(cls, value):
        """
        Implements the running (online) average of a metric across processes.
        """

        shared_val = cls._get_shared()
        shared_cnt = cls._get_shared_counter()
        try:
            with shared_cnt.get_lock(), shared_val.get_lock():
                shared_cnt.value += 1
                shared_val.value = shared_val.value + (value - shared_val.value) / shared_cnt.value
                current_val = shared_val.value
                current_cnt = shared_cnt.value
        except Exception:
            metric = cls.get_from_registry()
            metric.counter += 1
            metric.value = metric.value + (value - metric.value) / metric.counter
            current_val = metric.value
            current_cnt = metric.counter

        metric = cls.get_from_registry()
        metric.counter = current_cnt
        metric.value = current_val
        if cls.prometheus:
            cls.prometheus.set(current_val)


class ObservedMetric(StoredMetric):
    """
    Metric, that can be oberserved.
    """

    value = 0
    prometheus: Optional[Histogram] = None

    @classmethod
    def observe(cls, value):
        if cls.prometheus:
            cls.prometheus.observe(value)
        cls.set(value)
