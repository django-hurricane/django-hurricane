import asyncio

from hurricane.metrics.base import AverageMetric, CalculatedMetric, CounterMetric


class RequestCounterMetric(CounterMetric):
    code = "request_counter"


class ResponseTimeAverageMetric(AverageMetric):
    code = "response_time_average"


class RequestQueueLengthMetric(CalculatedMetric):
    code = "request_queue_length"

    def get_value(cls):
        return len(asyncio.all_tasks())
