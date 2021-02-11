from hurricane.metrics.exceptions import MetricIdAlreadyRegistered


class MetricsRegistry:

    """
    Registering metrics and storing them in a metrics dictionary.
    """

    def __init__(self):
        self.metrics = {}

    def register(self, metric_cls):
        if metric_cls.code in self.metrics:
            raise MetricIdAlreadyRegistered(f"Metric ID ({metric_cls.code}) is already registered.")
        self.metrics[metric_cls.code] = metric_cls()

    def unregister(self, metric_cls):
        try:
            del self.metrics[metric_cls.code]
        except KeyError:
            # TODO warn about trying to unregister not registered metric
            pass

    def get(self, code):
        return self.metrics[code]
