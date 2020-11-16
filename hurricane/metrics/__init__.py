from hurricane.metrics.registry import MetricsRegistry
from hurricane.metrics.requests import RequestCounterMetric, RequestQueueLengthMetric, ResponseTimeAverageMetric

registry = MetricsRegistry()

registry.register(RequestCounterMetric)
registry.register(RequestQueueLengthMetric)
registry.register(ResponseTimeAverageMetric)
