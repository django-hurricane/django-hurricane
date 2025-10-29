from hurricane.metrics.base import HurricaneMetric
from hurricane.metrics.exceptions import MetricIdAlreadyRegistered


class MetricsRegistry:
    """
    Registering metrics and storing them in a metrics dictionary.
    """

    def __init__(self) -> None:
        self.metrics: dict[str, HurricaneMetric] = {}

    def register(self, metric_cls: type[HurricaneMetric]):
        if metric_cls.code in self.metrics:
            raise MetricIdAlreadyRegistered(
                f"Metric ID ({metric_cls.code}) is already registered."
            )
        self.metrics[metric_cls.code] = metric_cls()

    def unregister(self, metric_cls: type[HurricaneMetric]):
        try:
            del self.metrics[metric_cls.code]
        except KeyError:
            # TODO warn about trying to unregister not registered metric
            pass

    def get(self, code: str) -> HurricaneMetric:
        return self.metrics[code]
