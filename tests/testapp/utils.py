from django.core.management.base import SystemCheckError
from django.db import OperationalError

CHECK_COUNT = 0
SYSTEM_COUNT = 0


def check_raise_operational_error(app_configs, **kwargs):
    global CHECK_COUNT

    if CHECK_COUNT > 0:
        raise OperationalError("Fake operational error")
    else:
        CHECK_COUNT += 1
        return []


def check_raise_systemcheck_error(app_configs, **kwargs):
    global SYSTEM_COUNT

    if SYSTEM_COUNT > 0:
        raise SystemCheckError("Fake system check error")
    else:
        SYSTEM_COUNT += 1
        return []
