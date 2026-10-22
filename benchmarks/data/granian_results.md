# Django-Hurricane Performance Report: Granian Engine
**Engine:** `granian` | **Version:** `1.6.2` | **Date:** `2026-10-20T13:25:12.809722+00:00`
**Environment:** Python `3.12.3` on `linux` (8 CPUs)

- **Initial Memory (RSS):** `168.21 MB`
- **Final Memory (RSS):** `180.65 MB`
- **Readiness 400 (Unready) Events:** `0` (flapping in Kubernetes)

## Scenarios Summary

| Scenario | Users | RPS | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) | Failures | Peak Memory (MB) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Standard Traffic Baseline** | 25 | 23.0 | 2.0 | 6.0 | 36.0 | 50.7 | 0 | 174.68 |
| **High Concurrency Saturation** | 80 | 633.4 | 120.0 | 160.0 | 180.0 | 213.6 | 0 | 180.98 |
| **Probe Responsiveness Under Heavy Load** | 50 | 630.9 | 66.0 | 97.0 | 120.0 | 154.0 | 0 | 180.98 |

## Endpoint Breakdown per Scenario

### Standard Traffic Baseline

| Endpoint | Method | Requests | RPS | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Failures |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | GET | 174 | 9.1 | 2.4 | 2.0 | 5.0 | 33.0 | 0 |
| `/alive` | GET | 58 | 3.0 | 2.3 | 2.0 | 5.0 | 28.0 | 0 |
| `/heavy` | GET | 32 | 1.7 | 5.1 | 3.0 | 12.0 | 50.0 | 0 |
| `/medium` | GET | 94 | 4.9 | 5.2 | 3.0 | 12.0 | 51.0 | 0 |
| `/ready` | GET | 80 | 4.2 | 2.2 | 2.0 | 5.0 | 25.0 | 0 |

### High Concurrency Saturation

| Endpoint | Method | Requests | RPS | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Failures |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | GET | 7561 | 397.5 | 105.3 | 120.0 | 140.0 | 170.0 | 0 |
| `/medium` | GET | 4488 | 235.9 | 121.3 | 130.0 | 160.0 | 190.0 | 0 |

### Probe Responsiveness Under Heavy Load

| Endpoint | Method | Requests | RPS | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Failures |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | GET | 7540 | 396.3 | 58.4 | 63.0 | 82.0 | 93.0 | 0 |
| `/alive` | GET | 71 | 3.7 | 55.8 | 56.0 | 84.0 | 94.0 | 0 |
| `/medium` | GET | 4308 | 226.4 | 75.1 | 77.0 | 110.0 | 120.0 | 0 |
| `/ready` | GET | 84 | 4.4 | 56.7 | 57.0 | 82.0 | 98.0 | 0 |

## Key Observations for Tornado Baseline
- **Latency Stacking Under Load:** When concurrency scales to 100 users, response times stack significantly as requests wait for threadpool slots.
- **Probe Contention:** Probes sharing the server pipeline experience increased latency under heavy user load.
- **Coroutine Allocation:** In-flight requests remain in memory as asyncio callbacks awaiting thread execution, inflating task counts.