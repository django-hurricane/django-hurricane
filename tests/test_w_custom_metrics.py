from prometheus_client.parser import text_string_to_metric_families

from hurricane.testing.testcases import HurricanServerTest


class HurricanStartServerTests(HurricanServerTest):
    metrics_route = "/metrics"
    starting_message = "Granian-powered Django web server"
    starting_http_message = "Starting Prometheus metrics exporter on port "

    @HurricanServerTest.cycle_server(env={"DJANGO_SETTINGS_MODULE": "tests.testapp.settings_metrics"})
    def test_custom_metrics(self):
        found_sync = False
        found_async = False
        res = self.probe_client.get(self.metrics_route)
        families = text_string_to_metric_families(res.text)
        for fam in families:
            if fam.name == "test_metric":
                found_sync = True
            if fam.name == "test_metric_async":
                found_async = True

        self.assertTrue(found_sync, msg="Synchronous metric not found in /metrics output")
        self.assertTrue(found_async, msg="Asynchronous metric not found in /metrics output")


class StoredMetricFloatPrecisionTests(HurricanServerTest):
    def test_float_zero_and_precision(self):
        from hurricane.metrics import registry
        from hurricane.metrics.base import StoredMetric

        class FloatMetric(StoredMetric):
            code = "test_float_metric"
            value = 0.0

        try:
            registry.register(FloatMetric)
        except Exception:
            registry.unregister(FloatMetric)
            registry.register(FloatMetric)

        FloatMetric.set(0.0)
        self.assertEqual(FloatMetric.get(), 0.0)

        FloatMetric.set(42.125)
        self.assertEqual(FloatMetric.get(), 42.125)

        FloatMetric.set(-7.5)
        self.assertEqual(FloatMetric.get(), -7.5)
