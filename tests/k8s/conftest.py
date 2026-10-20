import os
import subprocess
from pathlib import Path

import pytest
from pytest_kubernetes.providers import select_provider_manager

CLUSTER_NAME = "hurricane-test"


@pytest.fixture(scope="session")
def k8s():
    """
    Session-scoped Kubernetes manager using k3d.
    Ensures k3d cluster exists, imports the test image, and provides the manager.
    """
    manager_cls = select_provider_manager("k3d")
    manager = manager_cls(CLUSTER_NAME)

    # Check if cluster already exists
    out = subprocess.run(["k3d", "cluster", "list"], capture_output=True, text=True).stdout
    if CLUSTER_NAME not in out:
        manager.create()

    # Ensure kubeconfig is set
    kubeconfig_out = subprocess.run(
        ["k3d", "kubeconfig", "write", CLUSTER_NAME], capture_output=True, text=True
    ).stdout.strip()
    if kubeconfig_out and os.path.exists(kubeconfig_out):
        os.environ["KUBECONFIG"] = kubeconfig_out
        manager._cluster_options.kubeconfig_path = kubeconfig_out

    # Load test docker image into cluster
    subprocess.run(["k3d", "image", "import", "django-hurricane-test:latest", "-c", CLUSTER_NAME], check=True)

    yield manager
