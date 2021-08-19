import os

from .settings import *
from .settings import BASE_DIR

DEBUG = False


MEDIA_ROOT = os.path.join(BASE_DIR, "tests/testapp/test_media/")
