import tracemalloc

import pkg_resources  # type: ignore

tracemalloc.start()

HURRICANE_DIST_VERSION = pkg_resources.get_distribution("django-hurricane").version
