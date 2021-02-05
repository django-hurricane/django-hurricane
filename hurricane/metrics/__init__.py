from hurricane.metrics.registry import MetricsRegistry
from hurricane.metrics.requests import (
    RequestCounterMetric,
    RequestQueueLengthMetric,
    ResponseTimeAverageMetric,
    StartupTimeMetric,
)

registry = MetricsRegistry()

registry.register(RequestCounterMetric)
registry.register(RequestQueueLengthMetric)
registry.register(ResponseTimeAverageMetric)
registry.register(StartupTimeMetric)
