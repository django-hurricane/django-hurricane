import hurricane.server

from .settings import *


def fake_check_databases():
    raise Exception("Fake check databases exception")


hurricane.server.check_databases = fake_check_databases
