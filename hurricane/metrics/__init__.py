from hurricane.metrics.registry import MetricsRegistry
from hurricane.metrics.requests import (
    HealthMetric,
    InfoMetrics,
    PathCounterMetric,
    ReadinessMetric,
    RequestCounterMetric,
    RequestQueueLengthMetric,
    ResponseSizeMetric,
    ResponseTimeAverageMetric,
    ResponseTimeMetric,
    StartupTimeMetric,
)

registry = MetricsRegistry()

registry.register(RequestCounterMetric)
registry.register(RequestQueueLengthMetric)
registry.register(ResponseTimeAverageMetric)
registry.register(StartupTimeMetric)
registry.register(HealthMetric)
registry.register(ReadinessMetric)
registry.register(ResponseTimeMetric)
registry.register(ResponseSizeMetric)
registry.register(PathCounterMetric)
registry.register(InfoMetrics)
