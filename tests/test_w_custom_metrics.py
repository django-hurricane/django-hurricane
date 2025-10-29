from prometheus_client.parser import text_string_to_metric_families

from hurricane.testing.testcases import HurricanServerTest


class HurricanStartServerTests(HurricanServerTest):
    metrics_route = "/metrics"
    starting_message = "Tornado-powered Django web server"
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
