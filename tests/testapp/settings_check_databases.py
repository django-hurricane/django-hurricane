import django.db.backends.sqlite3.base
from django.db import connections

from .settings import *


def fake_cursor_execute(self, *args, **kwargs):
    raise Exception("Fake cursor execute exception")


django.db.backends.sqlite3.base.SQLiteCursorWrapper.execute = fake_cursor_execute
