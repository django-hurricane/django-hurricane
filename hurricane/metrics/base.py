class StoredMetric:
    code = None
    value = None

    def __init__(self, code=None, initial=None):
        if code:
            self.code = code
        if initial:
            self.value = initial

    @classmethod
    def get_from_registry(cls):
        from hurricane.metrics import registry

        return registry.get(cls.code)

    @classmethod
    def set(cls, value):
        metric = cls.get_from_registry()
        metric.value = value

    @classmethod
    def get(cls):
        metric = cls.get_from_registry()
        return metric.value


class CalculatedMetric:
    code = None

    def __init__(self, code=None):
        if code:
            self.code = code

    @classmethod
    def get_from_registry(cls):
        from hurricane.metrics import registry

        return registry.get(cls.code)

    @classmethod
    def get(cls):
        return cls.get_value(cls)

    @classmethod
    def get_value(cls):
        raise NotImplementedError


class CounterMetric(StoredMetric):
    value = 0

    @classmethod
    def increment(cls):
        cls.set(cls.get() + 1)

    @classmethod
    def decrement(cls):
        cls.set(cls.get() - 1)


class AverageMetric(StoredMetric):
    counter = 0
    value = 0

    @classmethod
    def add_value(cls, value):
        metric = cls.get_from_registry()
        metric.counter += 1
        metric.value = metric.value + (value - metric.value) / metric.counter
