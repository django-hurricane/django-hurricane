import os
import sys

DEBUG = True
SECRET_KEY = "thisisnotneeded"


INSTALLED_APPS = ["tests.testapp", "hurricane"]

MIDDLEWARE = []

SITE_ID = 1

MEDIA_URL = "/media/"
STATIC_URL = "/static/"

ROOT_URLCONF = "tests.testapp.urls"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "console": {"format": "%(asctime)s %(levelname)-8s %(name)-12s %(message)s"}
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "stream": sys.stdout,
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "hurricane": {
            "handlers": ["console"],
            "level": os.getenv("HURRICANE_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "pika": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "mydatabase",
    }
}
