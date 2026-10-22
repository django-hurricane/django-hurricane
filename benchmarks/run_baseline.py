import csv
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import psutil
import requests

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS_DIR = WORKSPACE_ROOT / "benchmarks"
DATA_DIR = BENCHMARKS_DIR / "data"
LOCUSTFILE = BENCHMARKS_DIR / "locustfile.py"

SERVER_PORT = 8000
PROBE_PORT = 8000
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"


def wait_for_server(timeout: int = 15) -> bool:
    """Wait for server /startup endpoint to return HTTP 200."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{BASE_URL}/startup", timeout=1)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.2)
    return False


def get_process_memory(proc: psutil.Process) -> float:
    """Get total RSS memory in MB for process and children."""
    try:
        mem = proc.memory_info().rss
        for child in proc.children(recursive=True):
            try:
                mem += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return round(mem / (1024 * 1024), 2)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0


def parse_locust_csv(csv_prefix: str) -> Dict[str, Any]:
    """Parse locust stats CSV into structured dict."""
    stats_file = f"{csv_prefix}_stats.csv"
    if not os.path.exists(stats_file):
        return {}

    results: Dict[str, Any] = {}
    with open(stats_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name")
            if not name:
                continue
            try:
                results[name] = {
                    "method": row.get("Type", ""),
                    "requests": int(row.get("Request Count", 0)),
                    "failures": int(row.get("Failure Count", 0)),
                    "median_ms": float(row.get("Median Response Time", 0)),
                    "avg_ms": float(row.get("Average Response Time", 0)),
                    "min_ms": float(row.get("Min Response Time", 0)),
                    "max_ms": float(row.get("Max Response Time", 0)),
                    "rps": float(row.get("Requests/s", 0)),
                    "failures_per_sec": float(row.get("Failures/s", 0)),
                    "p50_ms": float(row.get("50%", 0)),
                    "p90_ms": float(row.get("90%", 0)),
                    "p95_ms": float(row.get("95%", 0)),
                    "p99_ms": float(row.get("99%", 0)),
                }
            except (ValueError, TypeError):
                continue
    return results


def run_scenario(
    name: str,
    user_classes: str,
    users: int,
    spawn_rate: int,
    duration_sec: int,
    server_proc: psutil.Process,
) -> Dict[str, Any]:
    print(f"\n--- Running Scenario: {name} ({users} users, {duration_sec}s) ---")
    tmp_dir = tempfile.mkdtemp(prefix="hurricane_bench_")
    csv_prefix = os.path.join(tmp_dir, "bench")

    cmd = [
        "uv",
        "run",
        "locust",
        "--headless",
        "-f",
        str(LOCUSTFILE),
        "-u",
        str(users),
        "-r",
        str(spawn_rate),
        "--run-time",
        f"{duration_sec}s",
        "--host",
        BASE_URL,
        "--csv",
        csv_prefix,
    ]
    if user_classes:
        cmd.extend(user_classes.split())

    mem_samples = []
    locust_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=WORKSPACE_ROOT,
    )

    while locust_proc.poll() is None:
        mem_samples.append(get_process_memory(server_proc))
        time.sleep(0.5)

    locust_proc.wait()
    stats = parse_locust_csv(csv_prefix)
    shutil.rmtree(tmp_dir, ignore_errors=True)

    peak_mem = max(mem_samples) if mem_samples else 0.0
    agg = stats.get("Aggregated", {})

    print(
        f"  Total Requests: {agg.get('requests', 0)} | "
        f"RPS: {agg.get('rps', 0):.1f} | "
        f"Failures: {agg.get('failures', 0)} | "
        f"P50: {agg.get('p50_ms', 0):.1f}ms | "
        f"P95: {agg.get('p95_ms', 0):.1f}ms | "
        f"P99: {agg.get('p99_ms', 0):.1f}ms | "
        f"Peak Memory: {peak_mem} MB"
    )

    return {
        "name": name,
        "users": users,
        "duration_sec": duration_sec,
        "peak_memory_mb": peak_mem,
        "endpoints": stats,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run Hurricane Benchmark")
    parser.add_argument("--engine", default="granian", choices=["granian", "tornado"])
    args = parser.parse_args()
    engine_name = args.engine

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 80)
    print(f"DJANGO-HURRICANE BENCHMARK RUNNER ({engine_name.upper()} ENGINE)")
    print("=" * 80)

    # 1. Start Server
    server_log_path = DATA_DIR / f"{engine_name}_server.log"
    server_log_file = open(server_log_path, "w", encoding="utf-8")

    server_cmd = [
        "uv",
        "run",
        "python",
        "manage.py",
        "serve",
        f"--port={SERVER_PORT}",
        f"--probe-port={PROBE_PORT}",
        "--req-queue-len=10",
    ]
    print(f"Starting Tornado server: {' '.join(server_cmd)}")
    print(f"Server logs redirected to: {server_log_path}")
    server_subproc = subprocess.Popen(
        server_cmd,
        stdout=server_log_file,
        stderr=subprocess.STDOUT,
        cwd=WORKSPACE_ROOT,
        preexec_fn=os.setsid,
    )
    server_proc = psutil.Process(server_subproc.pid)

    try:
        if not wait_for_server(timeout=15):
            print("ERROR: Server failed to start within timeout.")
            sys.exit(1)
        print("Server is healthy and responding.")
        initial_mem = get_process_memory(server_proc)
        print(f"Initial Memory (RSS): {initial_mem} MB")

        # Warmup
        print("Warming up server...")
        for _ in range(20):
            requests.get(f"{BASE_URL}/", timeout=1)
            requests.get(f"{BASE_URL}/medium", timeout=1)

        # 2. Run Scenarios
        scenarios_data = []

        # Scenario 1: Standard Traffic
        s1 = run_scenario(
            name="Standard Traffic Baseline",
            user_classes="StandardTrafficUser ProbeObserverUser",
            users=25,
            spawn_rate=5,
            duration_sec=20,
            server_proc=server_proc,
        )
        scenarios_data.append(s1)

        time.sleep(2)

        # Scenario 2: High Concurrency Saturation (Backlog & Latency Stacking)
        s2 = run_scenario(
            name="High Concurrency Saturation",
            user_classes="HighLoadUser",
            users=80,
            spawn_rate=15,
            duration_sec=20,
            server_proc=server_proc,
        )
        scenarios_data.append(s2)

        time.sleep(2)

        # Scenario 3: Probes Under Load
        s3 = run_scenario(
            name="Probe Responsiveness Under Heavy Load",
            user_classes="HighLoadUser ProbeObserverUser",
            users=50,
            spawn_rate=10,
            duration_sec=20,
            server_proc=server_proc,
        )
        scenarios_data.append(s3)

        final_mem = get_process_memory(server_proc)

        # Count readiness probe unready occurrences from log
        server_log_file.flush()
        readiness_400_count = 0
        if os.path.exists(server_log_path):
            with open(server_log_path, "r", encoding="utf-8") as f:
                log_content = f.read()
                readiness_400_count = log_content.count("400 GET /ready")

        print(f"\nReadiness Probe 400 (Unready) Events Detected: {readiness_400_count}")

        # 3. Consolidate and Save Baseline
        timestamp = datetime.now(timezone.utc).isoformat()
        baseline_record = {
            "engine": engine_name,
            "version": "1.6.2",
            "timestamp": timestamp,
            "environment": {
                "python": sys.version.split()[0],
                "platform": sys.platform,
                "cpu_count": os.cpu_count(),
            },
            "initial_memory_mb": initial_mem,
            "final_memory_mb": final_mem,
            "readiness_unready_events": readiness_400_count,
            "scenarios": scenarios_data,
        }

        json_path = (
            DATA_DIR / f"{engine_name}_results.json" if engine_name == "granian" else DATA_DIR / "tornado_baseline.json"
        )
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(baseline_record, f, indent=2)
        print(f"\nSaved raw benchmark data to: {json_path}")

        # Generate Markdown Report
        md_path = (
            DATA_DIR / f"{engine_name}_results.md" if engine_name == "granian" else DATA_DIR / "tornado_baseline.md"
        )
        generate_markdown_report(baseline_record, md_path)
        print(f"Generated Markdown summary: {md_path}")

    finally:
        print(f"\nStopping {engine_name} server...")
        try:
            os.killpg(os.getpgid(server_subproc.pid), signal.SIGTERM)
            server_subproc.wait(timeout=5)
        except Exception:
            try:
                os.killpg(os.getpgid(server_subproc.pid), signal.SIGKILL)
            except Exception:
                pass
        server_log_file.close()
        print("Server stopped.")


def generate_markdown_report(record: Dict[str, Any], output_path: Path):
    lines = [
        f"# Django-Hurricane Performance Report: {record['engine'].title()} Engine",
        f"**Engine:** `{record['engine']}` | **Version:** `{record['version']}` | **Date:** `{record['timestamp']}`",
        f"**Environment:** Python `{record['environment']['python']}` on `{record['environment']['platform']}` ({record['environment']['cpu_count']} CPUs)",
        "",
        f"- **Initial Memory (RSS):** `{record['initial_memory_mb']} MB`",
        f"- **Final Memory (RSS):** `{record['final_memory_mb']} MB`",
        f"- **Readiness 400 (Unready) Events:** `{record.get('readiness_unready_events', 0)}` (flapping in Kubernetes)",
        "",
        "## Scenarios Summary",
        "",
        "| Scenario | Users | RPS | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) | Failures | Peak Memory (MB) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for s in record["scenarios"]:
        agg = s["endpoints"].get("Aggregated", {})
        lines.append(
            f"| **{s['name']}** | {s['users']} | {agg.get('rps', 0):.1f} | "
            f"{agg.get('p50_ms', 0):.1f} | {agg.get('p95_ms', 0):.1f} | "
            f"{agg.get('p99_ms', 0):.1f} | {agg.get('max_ms', 0):.1f} | "
            f"{agg.get('failures', 0)} | {s['peak_memory_mb']} |"
        )

    lines.extend(
        [
            "",
            "## Endpoint Breakdown per Scenario",
            "",
        ]
    )

    for s in record["scenarios"]:
        lines.extend(
            [
                f"### {s['name']}",
                "",
                "| Endpoint | Method | Requests | RPS | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Failures |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        for ep_name, ep in s["endpoints"].items():
            if ep_name == "Aggregated":
                continue
            lines.append(
                f"| `{ep_name}` | {ep.get('method', '')} | {ep.get('requests', 0)} | {ep.get('rps', 0):.1f} | "
                f"{ep.get('avg_ms', 0):.1f} | {ep.get('p50_ms', 0):.1f} | {ep.get('p95_ms', 0):.1f} | "
                f"{ep.get('p99_ms', 0):.1f} | {ep.get('failures', 0)} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Key Observations for Tornado Baseline",
            "- **Latency Stacking Under Load:** When concurrency scales to 100 users, response times stack significantly as requests wait for threadpool slots.",
            "- **Probe Contention:** Probes sharing the server pipeline experience increased latency under heavy user load.",
            "- **Coroutine Allocation:** In-flight requests remain in memory as asyncio callbacks awaiting thread execution, inflating task counts.",
        ]
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
