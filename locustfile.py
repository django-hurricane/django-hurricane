import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from locust import between, events, task
from locust.contrib.fasthttp import FastHttpUser


class HurricaneWebsiteUser(FastHttpUser):
    wait_time = between(5, 15)
    url = "/"
    weight = 1

    @task
    def request(self):
        self.client.get(self.url)


class MediumHurricaneWebsiteUser(HurricaneWebsiteUser):
    url = "/medium"
    weight = 3


class HeavyHurricaneWebsiteUser(HurricaneWebsiteUser):
    url = "/heavy"
    weight = 1


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument(
        "--baseline",
        type=str,
        default=os.environ.get("HURRICANE_BASELINE_FILE", "benchmarks/data/tornado_baseline.json"),
        help="Path to baseline JSON file for regression tracking",
    )
    parser.add_argument(
        "--max-regression-pct",
        type=float,
        default=float(os.environ.get("HURRICANE_MAX_REGRESSION_PCT", "100.0")),
        help="Allowed percentage degradation before failing (default: 100.0%%)",
    )


@events.quitting.add_listener
def _(environment, **kw):
    stats = environment.stats.total
    avg_resp = stats.avg_response_time
    p95_resp = stats.get_response_time_percentile(0.95)
    fail_ratio = stats.fail_ratio

    logging.info(
        f"Load test completed: {stats.num_requests} requests, {stats.num_failures} failures ({fail_ratio:.2%})"
    )
    logging.info(f"Average response time: {avg_resp:.2f} ms")
    logging.info(f"95th percentile response time: {p95_resp:.2f} ms")

    if fail_ratio > 0.025:
        logging.error(f"Test failed due to failure ratio {fail_ratio:.2%} > 2.5%")
        environment.process_exit_code = 1
        return

    baseline_path_str = getattr(environment.parsed_options, "baseline", None) or os.environ.get(
        "HURRICANE_BASELINE_FILE", "benchmarks/data/tornado_baseline.json"
    )
    max_regression_pct = float(
        getattr(environment.parsed_options, "max_regression_pct", None)
        or os.environ.get("HURRICANE_MAX_REGRESSION_PCT", "100.0")
    )

    baseline_file = Path(baseline_path_str) if baseline_path_str else None
    baseline_data: Dict[str, Any] = {}
    baseline_endpoints: Dict[str, Any] = {}

    if baseline_file and baseline_file.exists():
        try:
            with open(baseline_file, "r", encoding="utf-8") as f:
                baseline_data = json.load(f)
            for scen in baseline_data.get("scenarios", []):
                if scen.get("users") == 25 or "Standard" in scen.get("name", ""):
                    baseline_endpoints = scen.get("endpoints", {})
                    break
            if not baseline_endpoints and baseline_data.get("scenarios"):
                baseline_endpoints = baseline_data["scenarios"][0].get("endpoints", {})
        except Exception as e:
            logging.warning(f"Could not load baseline file {baseline_file}: {e}")

    if baseline_endpoints:
        multiplier = 1.0 + (max_regression_pct / 100.0)
        has_regression = False

        logging.info(
            f"Validating performance against baseline '{baseline_file.name}' (+{max_regression_pct:.1f}% tolerance):"
        )

        for key, entry in environment.stats.entries.items():
            ep_name = key[0]
            if ep_name not in baseline_endpoints:
                continue

            base_ep = baseline_endpoints[ep_name]
            base_avg = float(base_ep.get("avg_ms", 0))
            base_p95 = float(base_ep.get("p95_ms", 0))

            ep_avg = entry.avg_response_time
            ep_p95 = entry.get_response_time_percentile(0.95)

            logging.info(
                f"  - Endpoint {ep_name}: Avg={ep_avg:.2f}ms (baseline={base_avg:.2f}ms, limit={base_avg * multiplier:.2f}ms), "
                f"P95={ep_p95:.2f}ms (baseline={base_p95:.2f}ms, limit={base_p95 * multiplier:.2f}ms)"
            )

            if base_avg > 0 and ep_avg > (base_avg * multiplier):
                diff = ((ep_avg - base_avg) / base_avg) * 100.0
                logging.error(
                    f"Performance regression on {ep_name} Avg: {ep_avg:.2f}ms exceeds baseline {base_avg:.2f}ms by {diff:+.1f}%"
                )
                has_regression = True

            if base_p95 > 0 and ep_p95 > (base_p95 * multiplier):
                diff = ((ep_p95 - base_p95) / base_p95) * 100.0
                logging.error(
                    f"Performance regression on {ep_name} P95: {ep_p95:.2f}ms exceeds baseline {base_p95:.2f}ms by {diff:+.1f}%"
                )
                has_regression = True

        if has_regression:
            logging.error(f"Load test FAILED: Performance regressions exceeded threshold of {max_regression_pct:.1f}%.")
            environment.process_exit_code = 1
        else:
            logging.info("Performance check PASSED: All endpoint latencies within baseline limits.")
            environment.process_exit_code = 0
    else:
        logging.warning("No baseline loaded; falling back to static thresholds (avg <= 350ms, p95 <= 950ms)")
        if avg_resp > 350:
            logging.error(f"Test failed due to average response time {avg_resp:.2f}ms > 350ms")
            environment.process_exit_code = 1
        elif p95_resp > 950:
            logging.error(f"Test failed due to 95th percentile response time {p95_resp:.2f}ms > 950ms")
            environment.process_exit_code = 1
        else:
            environment.process_exit_code = 0
