import asyncio

from hurricane.metrics.base import AverageMetric, CalculatedMetric, CounterMetric, StoredMetric


class RequestCounterMetric(CounterMetric):

    """
    Defines request counter metric with corresponding metric code.
    """

    code = "request_counter"


class ResponseTimeAverageMetric(AverageMetric):

    """
    Defines response time average metric with corresponding metric code.
    """

    code = "response_time_average"


class RequestQueueLengthMetric(CalculatedMetric):

    """
    Defines request queue length metric with corresponding metric code.
    """

    code = "request_queue_length"

    def get_value(self):

        """
        Getting length of the asyncio queue of all tasks.
        """

        return len(asyncio.all_tasks())


class StartupTimeMetric(StoredMetric):
    code = "startup_time"


class HealthMetric(StoredMetric):
    code = "health"


class ReadinessMetric(StoredMetric):
    code = "readiness"
