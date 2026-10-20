# Django-Hurricane Baseline Performance Report: Tornado Engine
**Engine:** `tornado` | **Version:** `1.6.2` | **Date:** `2026-10-20T09:18:33.017166+00:00`
**Environment:** Python `3.12.3` on `linux` (8 CPUs)

- **Initial Memory (RSS):** `53.65 MB`
- **Final Memory (RSS):** `65.44 MB`
- **Readiness 400 (Unready) Events:** `160` (flapping in Kubernetes)

## Scenarios Summary

| Scenario | Users | RPS | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) | Failures | Peak Memory (MB) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Standard Traffic Baseline** | 25 | 22.3 | 3.0 | 12.0 | 22.0 | 36.0 | 0 | 57.96 |
| **High Concurrency Saturation** | 80 | 416.6 | 160.0 | 240.0 | 280.0 | 376.0 | 0 | 65.22 |
| **Probe Responsiveness Under Heavy Load** | 50 | 313.3 | 130.0 | 200.0 | 220.0 | 303.0 | 0 | 65.43 |

## Endpoint Breakdown per Scenario

### Standard Traffic Baseline

| Endpoint | Method | Requests | RPS | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Failures |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | GET | 168 | 8.8 | 3.8 | 3.0 | 12.0 | 17.0 | 0 |
| `/alive` | GET | 58 | 3.1 | 2.7 | 2.0 | 10.0 | 16.0 | 0 |
| `/heavy` | GET | 24 | 1.3 | 6.2 | 4.0 | 14.0 | 36.0 | 0 |
| `/medium` | GET | 94 | 4.9 | 6.6 | 5.0 | 19.0 | 33.0 | 0 |
| `/ready` | GET | 80 | 4.2 | 2.1 | 2.0 | 7.0 | 10.0 | 0 |

### High Concurrency Saturation

| Endpoint | Method | Requests | RPS | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Failures |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | GET | 4925 | 258.9 | 160.3 | 160.0 | 230.0 | 270.0 | 0 |
| `/medium` | GET | 2998 | 157.6 | 179.4 | 180.0 | 260.0 | 290.0 | 0 |

### Probe Responsiveness Under Heavy Load

| Endpoint | Method | Requests | RPS | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Failures |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | GET | 3545 | 186.3 | 121.6 | 130.0 | 180.0 | 200.0 | 0 |
| `/alive` | GET | 76 | 4.0 | 84.9 | 97.0 | 140.0 | 170.0 | 0 |
| `/medium` | GET | 2268 | 119.2 | 144.3 | 150.0 | 210.0 | 240.0 | 0 |
| `/ready` | GET | 72 | 3.8 | 74.0 | 77.0 | 140.0 | 160.0 | 0 |

## Key Observations for Tornado Baseline
- **Latency Stacking Under Load:** When concurrency scales to 100 users, response times stack significantly as requests wait for threadpool slots.
- **Probe Contention:** Probes sharing the server pipeline experience increased latency under heavy user load.
- **Coroutine Allocation:** In-flight requests remain in memory as asyncio callbacks awaiting thread execution, inflating task counts.