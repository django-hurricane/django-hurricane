# -*- coding: utf-8 -*-
import os

from setuptools import find_packages, setup

base_dir = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(base_dir, "VERSION")) as f:
    VERSION = f.read()

with open(os.path.join(base_dir, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

DESCRIPTION = "Hurricane is an initiative to fit Django perfectly with Kubernetes."


setup(
    name="django-hurricane",
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type="text/markdown",
    version=VERSION,
    install_requires=["tornado~=6.1", "Django>=2.2", "asgiref~=3.4.0", "pika~=1.1.0", "requests~=2.25"],
    extras_require={
        "debug": ["debugpy~=1.5"],
        "pycharm": ["pydevd-pycharm~=213.5605.23"],
    },
    python_requires="~=3.8",
    packages=[
        "hurricane",
        "hurricane.amqp",
        "hurricane.metrics",
        "hurricane.server",
        "hurricane.webhooks",
        "hurricane.testing",
        "hurricane.management",
        "hurricane.management.commands",
    ],
    author="Michael Schilonka",
    author_email="michael@blueshoe.de",
    include_package_data=True,
    url="https://github.com/Blueshoe/django-hurricane",
    project_urls={
        "Source": "https://github.com/Blueshoe/django-hurricane",
        "Documentation": "https://django-hurricane.readthedocs.io/en/latest/",
        "Bug Tracker": "https://github.com/Blueshoe/django-hurricane/issues",
    },
    classifiers=[
        "Intended Audience :: Developers",
        "Topic :: Software Development",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 2.2",
        "Framework :: Django :: 3.0",
        "Framework :: Django :: 3.1",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
    ],
)
