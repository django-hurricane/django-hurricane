import os

from .settings import *

os.environ["AMQP_HOST"] = "test"
os.environ["AMQP_PORT"] = "8020"
os.environ["AMQP_VHOST"] = "test"
os.environ["AMQP_USER"] = "Test"
os.environ["AMQP_PASSWORD"] = "test"
