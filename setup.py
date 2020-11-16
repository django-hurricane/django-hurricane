# -*- coding: utf-8 -*-
import os

from setuptools import find_packages, setup

with open("VERSION") as v_file:
    VERSION = v_file.read()

DESCRIPTION = "Django Hurricane is an initiative to make Django more cloud-native compatible."


setup(
    name="django-hurricane",
    description=DESCRIPTION,
    version=VERSION,
    install_requires=[
        "tornado~=6.1",
        "Django>=2.2",
    ],
    python_requires="~=3.8",
    packages=[
        "hurricane",
        "hurricane.management",
        "hurricane.management.commands",
    ],
    author="Michael Schilonka",
    author_email="michael@blueshoe.de",
    include_package_data=True,
    classifiers=[
        "Intended Audience :: Developers",
        "Topic :: Software Development",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 2.2",
        "Framework :: Django :: 3.0",
        "Framework :: Django :: 3.1" "",
        "Programming Language :: Python :: 3.8",
    ],
)
