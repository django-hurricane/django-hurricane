from django.core.checks import register

import tests.testapp.utils as utils

from .settings import *

DEBUG = False

register(utils.check_raise_operational_error, "liveness")
