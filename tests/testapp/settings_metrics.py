from prometheus_client import Counter
from .settings import *

from hurricane.metrics import registry
from hurricane.metrics.base import CounterMetric, CalculatedMetric


class TestMetric(CounterMetric):
        code = "test_metric"
        description = "A test counter metric"
        prometheus = Counter('test_metric', 'Description of counter') 


class TestAsyncMetric(CalculatedMetric):
        code = "test_metric_async"
        description = "A test async counter metric"
        prometheus = Counter('test_metric_async', 'Description of async counter') 
        is_async = True

        @classmethod
        async def get(cls):
            # Simulate an asynchronous computation
            import asyncio
            await asyncio.sleep(0.1)
            return 42



registry.register(TestMetric)
registry.register(TestAsyncMetric)

TestMetric.increment()
