import unittest

from prometheus_client import Histogram

from hurricane.metrics import registry
from hurricane.metrics.base import AverageMetric, ObservedMetric
from hurricane.metrics.shared import SharedMetrics


class CustomObservedMetric(ObservedMetric):
    code = "custom_observed"
    prometheus = Histogram("custom_observed_histogram", "Custom histogram")


class CustomAverageMetric(AverageMetric):
    code = "custom_average"


registry.register(CustomObservedMetric)
registry.register(CustomAverageMetric)


class SharedMetricsTests(unittest.TestCase):
    def setUp(self):
        SharedMetrics.reset()

    def tearDown(self):
        SharedMetrics.reset()

    def test_request_counter_operations(self):
        initial = SharedMetrics.get_requests()
        val1 = SharedMetrics.increment_requests()
        self.assertEqual(val1, initial + 1)
        val2 = SharedMetrics.increment_requests()
        self.assertEqual(val2, initial + 2)
        self.assertEqual(SharedMetrics.get_requests(), initial + 2)

    def test_response_time_running_average(self):
        avg1 = SharedMetrics.add_response_time(10.0)
        self.assertAlmostEqual(avg1, 10.0, places=2)
        avg2 = SharedMetrics.add_response_time(20.0)
        self.assertAlmostEqual(avg2, 15.0, places=2)
        avg3 = SharedMetrics.add_response_time(30.0)
        self.assertAlmostEqual(avg3, 20.0, places=2)
        self.assertAlmostEqual(SharedMetrics.get_average_response_time(), 20.0, places=2)

    def test_startup_time_operations(self):
        SharedMetrics.set_startup_time(1.234)
        val = SharedMetrics.get_startup_time()
        self.assertIsNotNone(val)
        self.assertAlmostEqual(val, 1.234, places=3)

        SharedMetrics.set_startup_time(0.0)
        self.assertIsNone(SharedMetrics.get_startup_time())

    def test_readiness_flag(self):
        SharedMetrics.set_readiness(True)
        self.assertTrue(SharedMetrics.get_readiness())
        SharedMetrics.set_readiness(False)
        self.assertFalse(SharedMetrics.get_readiness())

    def test_liveness_flag(self):
        SharedMetrics.set_health(True)
        self.assertTrue(SharedMetrics.get_health())
        SharedMetrics.set_health(False)
        self.assertFalse(SharedMetrics.get_health())

    def test_track_request_lifecycle_and_backlog(self):
        # max_threads = 2
        # First request: 1 in flight, backlog 0
        backlog = SharedMetrics.track_request_start(max_threads=2)
        self.assertEqual(backlog, 0)
        self.assertEqual(SharedMetrics.get_in_flight(), 1)
        self.assertEqual(SharedMetrics.get_queue_length(), 0)

        # Second request: 2 in flight, backlog 1
        backlog = SharedMetrics.track_request_start(max_threads=2)
        self.assertEqual(backlog, 1)
        self.assertEqual(SharedMetrics.get_in_flight(), 2)

        # Third request: 3 in flight, backlog 2
        backlog = SharedMetrics.track_request_start(max_threads=2)
        self.assertEqual(backlog, 2)
        self.assertEqual(SharedMetrics.get_in_flight(), 3)
        self.assertEqual(SharedMetrics.get_queue_length(), 2)

        # Complete third request
        SharedMetrics.track_request_end(max_threads=2)
        self.assertEqual(SharedMetrics.get_in_flight(), 2)
        self.assertEqual(SharedMetrics.get_queue_length(), 1)

        # Complete second and first request
        SharedMetrics.track_request_end(max_threads=2)
        SharedMetrics.track_request_end(max_threads=2)
        self.assertEqual(SharedMetrics.get_in_flight(), 0)
        self.assertEqual(SharedMetrics.get_queue_length(), 0)

    def test_observed_metric(self):
        CustomObservedMetric.observe(42.5)
        self.assertEqual(CustomObservedMetric.get(), 42.5)

    def test_average_metric_running_calculation(self):
        CustomAverageMetric.add_value(10.0)
        self.assertAlmostEqual(CustomAverageMetric.get(), 10.0, places=2)
        CustomAverageMetric.add_value(30.0)
        self.assertAlmostEqual(CustomAverageMetric.get(), 20.0, places=2)
