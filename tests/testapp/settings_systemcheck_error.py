from django.core.checks import register

import tests.testapp.utils as utils

from .settings import *

register(utils.check_raise_systemcheck_error, "liveness")
