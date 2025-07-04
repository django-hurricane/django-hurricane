import importlib.metadata

try:
    HURRICANE_DIST_VERSION = importlib.metadata.version("django-hurricane")
except importlib.metadata.PackageNotFoundError:
    raise RuntimeError("django-hurricane not found in environment.")
