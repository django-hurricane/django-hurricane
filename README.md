[![PyPI version](https://badge.fury.io/py/django-hurricane.svg)](https://badge.fury.io/py/django-hurricane)
[![CI Status](https://github.com/django-hurricane/django-hurricane/actions/workflows/ci.yml/badge.svg)](https://github.com/django-hurricane/django-hurricane/actions/workflows/ci.yml)
[![Coverage Status](https://coveralls.io/repos/github/django-hurricane/django-hurricane/badge.svg?branch=main)](https://coveralls.io/github/django-hurricane/django-hurricane?branch=main)
[![ReadTheDocs](https://readthedocs.org/projects/django-hurricane/badge/?version=latest)](https://django-hurricane.readthedocs.io/en/latest/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)
[![Powered by Rust](https://img.shields.io/badge/Rewritten%20in-Rust%20🦀-orange.svg)](https://github.com/emmett-framework/granian)

<br />

<div align="center">
  <img src="https://raw.githubusercontent.com/Blueshoe/django-hurricane/master/docs/_static/img/logo.png" alt="Django Hurricane Logo" width="220" />
  <h1 align="center">Hurricane</h1>
  <p align="center">
    <strong>The Kubernetes-Native Application Server for Django.</strong><br />
    <em>Now powered by Granian (Hyper / Tokio / Rust 🦀) with zero-config WSGI & ASGI support.</em>
  </p>
  <p align="center">
    <a href="https://django-hurricane.io/">Website</a> ·
    <a href="https://django-hurricane.readthedocs.io/en/latest/">Documentation</a> ·
    <a href="https://django-hurricane.readthedocs.io/en/latest/usage.html">User Guide</a>
  </p>
</div>

---

### "Did somebody say *Rewrite It In Rust*?" 🦀

As is required by Internet Law™, we felt the moral imperative to bring **Rust** into the Python ecosystem. 

Previous versions of Hurricane relied on Tornado to bridge asynchronous networking with Django's synchronous WSGI layer. While pioneering, Tornado's Python event loop occasionally threw tantrums under heavy concurrency-choking on WSGI thread transitions and flapping Kubernetes readiness probes with false queue-saturation warnings.

**We ripped that out.**

Hurricane is now powered by **[Granian](https://github.com/emmett-framework/granian)**, a lightning-fast HTTP server built directly on Rust’s **Hyper** and **Tokio** runtimes. You get:
- 🚀 **Blazingly fast** HTTP handling with zero-copy I/O.
- 🦀 **Rust concurrency** managing TCP connection pools and worker dispatch.
- 🧘 **True peace of mind:** Kubernetes probes that reflect actual server capacity rather than asyncio event loop panic.

---

## ⚡ Benchmarks: Tornado vs. Granian

We pit the classic Tornado-based Hurricane against the new Granian-powered engine using Locust under identical high-concurrency conditions:

| Metric | Tornado Baseline | Granian (New Engine) 🦀 | Difference |
| :--- | :---: | :---: | :---: |
| **False Readiness Failures (`HTTP 400`)** | **160 flapping events** | **0 events** | **-100.0% (Eliminated!)** |
| **Peak Throughput (RPS)** | 313.3 req/s | **630.9 req/s** | **+101.4% (2x faster)** |
| **P50 Median Latency** | 130.0 ms | **66.0 ms** | **-49.2% (Half the wait)** |
| **P99 Tail Latency** | 220.0 ms | **120.0 ms** | **-45.5% faster** |
| **Probe Latency Under Load** | 170.0 ms | **94.0 ms** | **-44.7% faster** |

*Under heavy traffic, Tornado mistook pending asyncio task counts for saturated request backlogs, triggering 160 false unready events that pulled pods out of service endpoints. Granian completely eliminates false unready flaps while doubling throughput.*

---

## ✨ Highlights & Features

### 🔌 Zero-Config WSGI & ASGI Auto-Detection
Whether you are running a classic synchronous Django app or a bleeding-edge async setup with Channels or streaming views, Hurricane **just works**:
- Got `WSGI_APPLICATION` in your settings? Hurricane boots with Granian's multithreaded WSGI runner.
- Configured `ASGI_APPLICATION`? Hurricane automatically switches to Granian's ASGI asynchronous engine.
- No manual `--mode` flags. No extra configuration files.

### 🛡️ First Line of Defense: Fast-404 Protection
Automated vulnerability scanners love hammering Django with `.php`, `/.env`, and `/wp-admin/` dictionary attacks. Normally, each attack request forces Django to execute its entire middleware stack, run session DB queries, and compile 404 templates.

Hurricane's **Fast-404 Engine** intercepts malicious and non-existent routes at the gateway edge:
- **Zero Django Overhead:** Serves your project's pre-rendered 404 HTML in **< 50 microseconds**, sparing Python worker threads and DB connection pools.
- **Anti-Django Signatures:** Immediately blocks scanner probes (`.php`, `/.env`, `/.git`, `wp-*`, `xmlrpc`, etc.).
- **CMS / Catch-All Aware:** Automatically detects root catch-alls (e.g. Wagtail, django-cms) and switches to signature-only matching so legitimate dynamic pages are never blocked.
- **Configurable:** Enabled by default (`auto`); easily disabled via `--no-fast-404` or `HURRICANE_FAST_404 = False`.

### ☸️ Native Kubernetes Probes
Kubernetes requires three probes to reliably manage container lifecycles. Hurricane implements all three out of the box without polluting your Django `urls.py`:
- **`/startup`**: Checks preflight tasks (like DB migrations) before Kubernetes allows traffic.
- **`/alive`**: Liveness probe ensuring the server process and worker threads aren't deadlocked.
- **`/ready`**: Verifies database connectivity and real request backlog capacity before routing traffic.

### 🛡️ Port Isolation with `--probe-port`
Running health checks on the same port as application traffic is a recipe for probe timeouts during traffic spikes. Hurricane allows isolating cluster probes on a separate port:
```bash
python manage.py serve --port 8000 --probe-port 8001
```
All probe requests run isolated on port 8001, synchronized with worker metrics via process-safe **Shared Memory**. Kubelet never times out waiting behind bulky user file downloads.

### 📊 Prometheus Metrics Built-In
Scrape `/metrics` out of the box! Hurricane exposes:
- Request counts, error rates, and average response times.
- Real-time worker thread saturation and backlog queue lengths.
- Standard Python runtime and GC allocation metrics.

### 📦 Static & Media File Serving
Don't want to run an Nginx sidecar just to serve media uploads and CSS?
```bash
python manage.py serve --static --media
```
Hurricane serves your collected statics and media assets directly with streaming responses.

### 🚀 Pre-Flight Migrations
Never serve traffic against an un-migrated database schema again:
```bash
python manage.py serve --check-migrations-apply
```
Hurricane runs pending migrations during startup while holding the `/startup` probe in a waiting state. Traffic is only allowed once the database schema is complete.

---

## 🚀 Quickstart

### 1. Installation

Install via `uv` (recommended) or `pip`:

```bash
# Using astral uv:
uv add django-hurricane

# Or using pip:
pip install django-hurricane
```

### 2. Configure Django

Add `"hurricane"` to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    "hurricane",
]
```

### 3. Start the Server

```bash
python manage.py serve
```

Watch Hurricane spin up with Granian:

```text
2026-10-20 12:00:00,102 INFO     hurricane.server.general Granian-powered Django web server. Version: 1.6.2
2026-10-20 12:00:00,103 INFO     hurricane.server.general Starting probe application running on port 8001 with route liveness-probe: /alive, readiness-probe: /ready, startup-probe: /startup
2026-10-20 12:00:00,103 INFO     hurricane.server.general Starting Prometheus metrics exporter on port 8001 with route /metrics
2026-10-20 12:00:00,215 INFO     hurricane.server.general Starting HTTP Server on port 8000
2026-10-20 12:00:00,216 INFO     hurricane.server.general Startup time is 0.113 seconds
```

---

## ☸️ Kubernetes Pod Example

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-django-app
spec:
  containers:
  - name: web
    image: my-django-image:latest
    command: ["python", "manage.py", "serve", "--port=8000", "--probe-port=8001", "--check-migrations-apply"]
    ports:
    - containerPort: 8000
      name: http
    - containerPort: 8001
      name: probes
    startupProbe:
      httpGet:
        path: /startup
        port: 8001
      failureThreshold: 30
      periodSeconds: 2
    livenessProbe:
      httpGet:
        path: /alive
        port: 8001
      periodSeconds: 5
    readinessProbe:
      httpGet:
        path: /ready
        port: 8001
      periodSeconds: 2
```

---

## 🛠️ Development & Testing

This project uses modern Python development tooling powered by **[uv](https://github.com/astral-sh/uv)** and **[ruff](https://github.com/astral-sh/ruff)**.

```bash
# Install dependencies
uv sync --all-groups --all-extras

# Run linting & formatting checks
uv run poe lint

# Run Django unit tests
uv run coverage run manage.py test

# Run Kubernetes End-to-End tests on k3d
uv run poe test-k8s

# Run performance benchmark suite
uv run poe benchmark
```

---

## 🏢 Commercial Support

Hurricane is developed and maintained with ❤️ by [Blueshoe](https://www.blueshoe.de).

Need help optimizing your cloud-native Django deployment or Kubernetes architecture? Reach out to us at [hurricane@blueshoe.de](mailto:hurricane@blueshoe.de).
