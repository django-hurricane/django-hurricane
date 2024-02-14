from time import sleep

from hurricane.server.loggers import STRUCTLOG_ENABLED
from hurricane.testing.testcases import HurricanServerTest


class HurricanMemoryAllocationTests(HurricanServerTest):
    @HurricanServerTest.cycle_server(args=["--max-memory", "200"])
    def test_reload_on_max_memory(self):
        out, err = self.driver.get_output(read_all=True)
        if STRUCTLOG_ENABLED:
            self.assertIn(
                "Memory allocation check        active=True max_memory_mb=200", out
            )
        else:
            self.assertIn(
                "Starting memory allocation check with maximum memory set to 200 Mb",
                out,
            )

        for _ in range(60):
            self.app_client.get("/memory")
            out, _ = self.driver.get_output(read_all=True)
            if STRUCTLOG_ENABLED:
                if "Memory (rss) usage is too high. Restarting" in out:
                    break
            else:
                if (
                    "Memory (rss) usage is too high. Restarting. Current memory usage is"
                    in out
                ):
                    break
            sleep(1)
        else:
            raise AssertionError("No reload detected within 60 seconds")

    @HurricanServerTest.cycle_server
    def test_no_reload(self):
        for _ in range(10):
            out, _ = self.driver.get_output(read_all=True)
            if STRUCTLOG_ENABLED:
                if "Memory allocation check        active=False" in out:
                    break
            else:
                if "Starting without memory allocation check" in out:
                    break
            sleep(1)
        else:
            raise AssertionError("Memory allocation check message not logged with 10 attempts")

        for _ in range(60):
            self.app_client.get("/memory")
            out, _ = self.driver.get_output(read_all=True)
            if STRUCTLOG_ENABLED:
                if "Memory (rss) usage is too high. Restarting" in out:
                    raise AssertionError("Reload detected although not requested")
            else:
                if (
                    "Memory (rss) usage is too high. Restarting. Current memory usage is"
                    in out
                ):
                    raise AssertionError("Reload detected although not requested")
            sleep(1)
