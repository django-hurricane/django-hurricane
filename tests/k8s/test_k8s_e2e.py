import concurrent.futures
import socket
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import requests
from pytest_kubernetes.providers import AClusterManager

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def wait_for_pod_ready(k8s: AClusterManager, pod_name: str, timeout: int = 60, namespace: str = "default"):
    """Wait for pod to reach Ready condition using pytest-kubernetes on-board wait method."""
    start = time.time()
    target = f"pod/{pod_name}"
    while time.time() - start < timeout:
        remaining = max(1, int(timeout - (time.time() - start)))
        try:
            k8s.wait(target, "condition=Ready", timeout=remaining, namespace=namespace)
            return k8s.kubectl(["get", "pod", pod_name, f"--namespace={namespace}"])
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(f"Pod {pod_name} did not become Ready within {timeout}s")


def wait_for_pod_container_ready(k8s: AClusterManager, pod_name: str, min_restarts: int = 1, timeout: int = 45):
    """Wait until container has restarted min_restarts times and is currently ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            pod = k8s.kubectl(["get", "pod", pod_name])
            c_status = pod.get("status", {}).get("containerStatuses", [{}])[0]
            restarts = c_status.get("restartCount", 0)
            ready = c_status.get("ready", False)
            if restarts >= min_restarts and ready:
                return pod
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(f"Pod {pod_name} did not reach ready state with min_restarts={min_restarts}")


def delete_pod_if_exists(k8s: AClusterManager, pod_name: str):
    try:
        k8s.kubectl(["delete", "pod", pod_name, "--now", "--ignore-not-found=true", "--wait=true"])
    except Exception:
        pass
    start = time.time()
    while time.time() - start < 10:
        try:
            k8s.kubectl(["get", "pod", pod_name])
            time.sleep(0.5)
        except Exception:
            break


def apply_fixture(k8s: AClusterManager, fixture_name: str):
    k8s.apply(FIXTURES_DIR / fixture_name)


@contextmanager
def forward_port(k8s: AClusterManager, pod_name: str, container_port: int):
    port = get_free_port()
    with k8s.port_forwarding(f"pod/{pod_name}", port, container_port):
        time.sleep(0.5)
        yield port


@pytest.mark.k8s
def test_k8s_happy_path_and_lifecycle(k8s: AClusterManager):
    """
    Test standard Kubernetes deployment happy path:
    - Pod starts, startupProbe succeeds, readinessProbe succeeds.
    - Application serves traffic on port 8000.
    - Prometheus metrics are exported.
    """
    pod_name = "hurricane-happy-path"
    delete_pod_if_exists(k8s, pod_name)
    apply_fixture(k8s, "happy_path.yaml")

    pod = wait_for_pod_ready(k8s, pod_name, timeout=45)
    assert pod["status"]["phase"] == "Running"

    with forward_port(k8s, pod_name, 8000) as local_port:
        resp = requests.get(f"http://127.0.0.1:{local_port}/", timeout=5)
        assert resp.status_code == 200
        assert "Hello world!" in resp.text

        metrics_resp = requests.get(f"http://127.0.0.1:{local_port}/metrics", timeout=5)
        assert metrics_resp.status_code == 200
        assert "request_counter" in metrics_resp.text

    restarts = k8s.kubectl(["get", "pod", pod_name])["status"]["containerStatuses"][0]["restartCount"]
    assert restarts == 0
    delete_pod_if_exists(k8s, pod_name)


@pytest.mark.k8s
def test_k8s_separate_probe_port(k8s: AClusterManager):
    """
    Test probe isolation with separate probe port:
    - Main service traffic on port 8000.
    - Kubernetes probes on port 8001.
    - Probe endpoints on port 8000 return 404 (confirming traffic/probe separation).
    """
    pod_name = "hurricane-separate-port"
    delete_pod_if_exists(k8s, pod_name)
    apply_fixture(k8s, "separate_probe_port.yaml")

    pod = wait_for_pod_ready(k8s, pod_name, timeout=45)
    assert pod["status"]["phase"] == "Running"

    # Main application port 8000
    with forward_port(k8s, pod_name, 8000) as app_port:
        resp = requests.get(f"http://127.0.0.1:{app_port}/", timeout=5)
        assert resp.status_code == 200
        assert "Hello world!" in resp.text

        # Probes on 8000 should return 404
        probe_on_app = requests.get(f"http://127.0.0.1:{app_port}/alive", timeout=5)
        assert probe_on_app.status_code == 404

    # Probe port 8001
    with forward_port(k8s, pod_name, 8001) as probe_port:
        alive_resp = requests.get(f"http://127.0.0.1:{probe_port}/alive", timeout=5)
        assert alive_resp.status_code == 200

        ready_resp = requests.get(f"http://127.0.0.1:{probe_port}/ready", timeout=5)
        assert ready_resp.status_code == 200

    delete_pod_if_exists(k8s, pod_name)


@pytest.mark.k8s
def test_k8s_intended_readiness_failure_under_backlog(k8s: AClusterManager):
    """
    Test intended readiness failure and traffic shedding:
    - When backlog exceeds --req-queue-len, /ready returns 400.
    - In Kubernetes, Pod flips to Ready: False (pulled from endpoints).
    - Container does NOT restart (restartCount remains 0).
    - Once backlog clears, /ready returns 200 and Pod flips back to Ready: True.
    """
    pod_name = "hurricane-readiness-failure"
    delete_pod_if_exists(k8s, pod_name)
    apply_fixture(k8s, "readiness_backlog.yaml")

    wait_for_pod_ready(k8s, pod_name, timeout=45)

    with forward_port(k8s, pod_name, 8000) as app_port, forward_port(k8s, pod_name, 8001) as probe_port:
        # Fire 6 concurrent requests to /slow (which sleeps for 1.5 seconds)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=6)
        futures = [executor.submit(requests.get, f"http://127.0.0.1:{app_port}/slow", timeout=10) for _ in range(6)]

        # Allow requests to hit the server and saturate the queue
        time.sleep(0.5)

        # While backlog is saturated, /ready must return 400 Bad Request
        ready_resp = requests.get(f"http://127.0.0.1:{probe_port}/ready", timeout=2)
        assert ready_resp.status_code == 400
        assert "Request queue limit exceeded" in ready_resp.text

        # Wait for all slow requests to complete (takes ~4.5s total across 2 workers)
        concurrent.futures.wait(futures, timeout=10)
        executor.shutdown()

        # Once queue is drained, /ready must return 200 OK
        time.sleep(1.0)
        recovered_resp = requests.get(f"http://127.0.0.1:{probe_port}/ready", timeout=2)
        assert recovered_resp.status_code == 200

    # Ensure container did not restart
    restarts = k8s.kubectl(["get", "pod", pod_name])["status"]["containerStatuses"][0]["restartCount"]
    assert restarts == 0
    delete_pod_if_exists(k8s, pod_name)


@pytest.mark.k8s
def test_k8s_intended_liveness_failure_and_container_healing(k8s: AClusterManager):
    """
    Test deadlock detection and self-healing in Kubernetes:
    - When worker threads block indefinitely, /alive fails/times out.
    - Kubernetes detects liveness failure and automatically restarts the container.
    - Container restartCount increases, and recovered container becomes Ready: True.
    """
    pod_name = "hurricane-liveness-healing"
    delete_pod_if_exists(k8s, pod_name)
    apply_fixture(k8s, "liveness_deadlock.yaml")

    wait_for_pod_ready(k8s, pod_name, timeout=45)

    with forward_port(k8s, pod_name, 8000) as port:
        # Trigger deadlock view (single worker sleeps for 300s)
        try:
            requests.get(f"http://127.0.0.1:{port}/deadlock", timeout=0.5)
        except (requests.Timeout, requests.RequestException):
            pass  # Expected: request blocks for 300s, client times out

    # Wait for container to be restarted by Kubernetes and become Ready again
    wait_for_pod_container_ready(k8s, pod_name, min_restarts=1, timeout=45)

    # Verify recovered pod serves traffic normally
    time.sleep(3)
    resp = None
    for _ in range(5):
        try:
            with forward_port(k8s, pod_name, 8000) as port:
                resp = requests.get(f"http://127.0.0.1:{port}/", timeout=5)
                if resp.status_code == 200:
                    break
        except Exception:
            time.sleep(2)

    assert resp is not None
    assert resp.status_code == 200
    assert "Hello world!" in resp.text

    delete_pod_if_exists(k8s, pod_name)


@pytest.mark.k8s
def test_k8s_static_and_media_serving(k8s: AClusterManager):
    """
    Test static and media asset serving inside Kubernetes:
    - Verifies Hurricane serves static and media assets without an external reverse proxy.
    """
    pod_name = "hurricane-static-media"
    delete_pod_if_exists(k8s, pod_name)
    apply_fixture(k8s, "static_media.yaml")

    wait_for_pod_ready(k8s, pod_name, timeout=45)

    with forward_port(k8s, pod_name, 8000) as port:
        # Test media file
        resp = requests.get(f"http://127.0.0.1:{port}/media/testfile.txt", timeout=5)
        assert resp.status_code == 200
        assert len(resp.content) > 0

        # Test static file
        static_resp = requests.get(f"http://127.0.0.1:{port}/static/logo.png", timeout=5)
        assert static_resp.status_code == 200
        assert "image" in static_resp.headers.get("content-type", "")

    delete_pod_if_exists(k8s, pod_name)
