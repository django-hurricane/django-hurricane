import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.testapp.settings")
django.setup()
