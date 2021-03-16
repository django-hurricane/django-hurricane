from hurricane.metrics.registry import MetricsRegistry
from hurricane.metrics.requests import (
    HealthMetric,
    ReadinessMetric,
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
registry.register(HealthMetric)
registry.register(ReadinessMetric)
