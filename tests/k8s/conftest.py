import os
import subprocess
from pathlib import Path

import pytest
from pytest_kubernetes.providers import AClusterManager, select_provider_manager

CLUSTER_NAME = "hurricane-test"


@pytest.fixture(scope="session")
def k8s():
    """
    Session-scoped Kubernetes manager using k3d.
    Ensures k3d cluster exists, imports the test image, and provides the manager.
    """
    manager_cls = select_provider_manager("k3d")
    manager: AClusterManager = manager_cls(CLUSTER_NAME)

    manager.create()

    os.environ["KUBECONFIG"] = str(manager.kubeconfig)

    # Load test docker image into cluster
    manager.load_image("django-hurricane-test:latest")

    yield manager

    manager.delete()
