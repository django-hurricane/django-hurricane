import json
import sys
from pathlib import Path
from typing import Any, Dict

DATA_DIR = Path(__file__).resolve().parent / "data"
BASELINE_PATH = DATA_DIR / "tornado_baseline.json"


def load_data(path: Path) -> Dict[str, Any]:
    if not path.exists():
        print(f"Error: File {path} not found.")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_delta(current: float, baseline: float, lower_is_better: bool = True) -> str:
    if baseline == 0:
        return "N/A"
    diff_pct = ((current - baseline) / baseline) * 100
    if lower_is_better:
        if diff_pct < 0:
            return f"\033[32m{diff_pct:.1f}%\033[0m"  # Green
        elif diff_pct > 0:
            return f"\033[31m+{diff_pct:.1f}%\033[0m"  # Red
        return "0.0%"
    else:
        if diff_pct > 0:
            return f"\033[32m+{diff_pct:.1f}%\033[0m"  # Green
        elif diff_pct < 0:
            return f"\033[31m{diff_pct:.1f}%\033[0m"  # Red
        return "0.0%"


def print_comparison(baseline: Dict[str, Any], current: Dict[str, Any]):
    print("=" * 96)
    print("DJANGO-HURRICANE COMPARATIVE BENCHMARK REPORT")
    print(f"Baseline: {baseline['engine']} {baseline['version']} ({baseline['timestamp']})")
    print(f"Current:  {current['engine']} {current.get('version', 'overhaul')} ({current['timestamp']})")
    print("=" * 96)

    print("\nOVERALL SUMMARY:")
    print(f"{'Metric':<35} {'Tornado (Baseline)':<22} {current['engine'] + ' (New)':<22} {'Change'}")
    print("-" * 96)

    # Readiness Unready Events
    base_unready = baseline.get("readiness_unready_events", 0)
    curr_unready = current.get("readiness_unready_events", 0)
    print(
        f"{'Readiness 400 (Unready) Events':<35} "
        f"{base_unready:<22} "
        f"{curr_unready:<22} "
        f"{format_delta(curr_unready, base_unready, lower_is_better=True)}"
    )

    # Peak memory
    base_mem = baseline.get("final_memory_mb", 0)
    curr_mem = current.get("final_memory_mb", 0)
    print(
        f"{'Peak RSS Memory (MB)':<35} "
        f"{base_mem:<22} "
        f"{curr_mem:<22} "
        f"{format_delta(curr_mem, base_mem, lower_is_better=True)}"
    )

    # Compare each scenario
    base_scenarios = {s["name"]: s for s in baseline.get("scenarios", [])}
    curr_scenarios = {s["name"]: s for s in current.get("scenarios", [])}

    for name, b_scen in base_scenarios.items():
        if name not in curr_scenarios:
            continue
        c_scen = curr_scenarios[name]
        print(f"\nSCENARIO: {name} ({b_scen['users']} Users)")
        print(f"{'Endpoint':<15} {'Metric':<18} {'Tornado':<18} {current['engine']:<18} {'Change'}")
        print("-" * 96)

        b_eps = b_scen["endpoints"]
        c_eps = c_scen["endpoints"]

        for ep in ["Aggregated", "/", "/medium", "/alive", "/ready"]:
            if ep not in b_eps or ep not in c_eps:
                continue
            b_data = b_eps[ep]
            c_data = c_eps[ep]

            # RPS
            print(
                f"{ep:<15} {'RPS':<18} "
                f"{b_data['rps']:<18.1f} "
                f"{c_data['rps']:<18.1f} "
                f"{format_delta(c_data['rps'], b_data['rps'], lower_is_better=False)}"
            )
            # P50
            print(
                f"{'':<15} {'P50 (ms)':<18} "
                f"{b_data['p50_ms']:<18.1f} "
                f"{c_data['p50_ms']:<18.1f} "
                f"{format_delta(c_data['p50_ms'], b_data['p50_ms'], lower_is_better=True)}"
            )
            # P99
            print(
                f"{'':<15} {'P99 (ms)':<18} "
                f"{b_data['p99_ms']:<18.1f} "
                f"{c_data['p99_ms']:<18.1f} "
                f"{format_delta(c_data['p99_ms'], b_data['p99_ms'], lower_is_better=True)}"
            )


def check_regressions(baseline: Dict[str, Any], current: Dict[str, Any], max_regression_pct: float = 25.0) -> bool:
    regressions = []
    base_scenarios = {s["name"]: s for s in baseline.get("scenarios", [])}
    curr_scenarios = {s["name"]: s for s in current.get("scenarios", [])}

    for name, b_scen in base_scenarios.items():
        if name not in curr_scenarios:
            continue
        c_scen = curr_scenarios[name]
        b_agg = b_scen["endpoints"].get("Aggregated", {})
        c_agg = c_scen["endpoints"].get("Aggregated", {})

        b_p95 = b_agg.get("p95_ms", 0)
        c_p95 = c_agg.get("p95_ms", 0)
        if b_p95 > 0 and c_p95 > b_p95 * (1 + max_regression_pct / 100):
            diff = ((c_p95 - b_p95) / b_p95) * 100
            regressions.append(f"{name} Aggregated P95: {c_p95:.1f}ms exceeds baseline {b_p95:.1f}ms (+{diff:.1f}%)")

        b_avg = b_agg.get("avg_ms", 0)
        c_avg = c_agg.get("avg_ms", 0)
        if b_avg > 0 and c_avg > b_avg * (1 + max_regression_pct / 100):
            diff = ((c_avg - b_avg) / b_avg) * 100
            regressions.append(f"{name} Aggregated Avg: {c_avg:.1f}ms exceeds baseline {b_avg:.1f}ms (+{diff:.1f}%)")

    if regressions:
        print("\n\033[31mPERFORMANCE REGRESSIONS DETECTED:\033[0m")
        for reg in regressions:
            print(f"  - {reg}")
        return False
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Compare Hurricane performance against baseline")
    parser.add_argument(
        "current",
        nargs="?",
        default=str(DATA_DIR / "granian_results.json"),
        help="Current benchmark results JSON",
    )
    parser.add_argument("--baseline", default=str(BASELINE_PATH), help="Baseline benchmark results JSON")
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit with non-zero status if performance regressed",
    )
    parser.add_argument(
        "--max-regression-pct",
        type=float,
        default=25.0,
        help="Allowed degradation percentage (default: 25%%)",
    )
    args = parser.parse_args()

    baseline = load_data(Path(args.baseline))
    current = load_data(Path(args.current))
    print_comparison(baseline, current)

    if args.fail_on_regression:
        passed = check_regressions(baseline, current, args.max_regression_pct)
        if not passed:
            print(f"\nFailed: Performance regressions exceeded threshold of {args.max_regression_pct}%.")
            sys.exit(1)
        print(f"\nPassed: All performance metrics within {args.max_regression_pct}% of baseline.")


if __name__ == "__main__":
    main()
