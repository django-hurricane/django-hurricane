[![PyPI version](https://badge.fury.io/py/django-hurricane.svg)](https://badge.fury.io/py/django-hurricane) ![Build Status](https://github.com/django-hurricane/django-hurricane/actions/workflows/python-app.yml/badge.svg) [![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=django-hurricane_django-hurricane&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=django-hurricane_django-hurricane) [![Coverage Status](https://coveralls.io/repos/github/django-hurricane/django-hurricane/badge.svg?branch=main)](https://coveralls.io/github/django-hurricane/django-hurricane?branch=main) [![ReadTheDocs](https://readthedocs.org/projects/django-hurricane/badge/?version=latest)](https://django-hurricane.readthedocs.io/en/latest/) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
--------------------------------------------------------------------------------
<br />
<br />

![Hurricane Logo](https://raw.githubusercontent.com/Blueshoe/django-hurricane/master/docs/_static/img/logo.png)

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <h3 align="center">Hurricane</h3>

  <p align="center">
    An initiative to fit Django perfectly with Kubernetes. It is supposed to cover many capabilities in order to run 
    Django in a cloud-native environment, including a Tornado-powered Django app server.
    <br />
    <a href="https://django-hurricane.readthedocs.io/en/latest/"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://django-hurricane.io/">Hurricane website</a>
    ·
    <a href="https://django-hurricane.readthedocs.io/en/latest/usage.html">User's guide</a>
    ·
    <a href="https://django-hurricane.io/basic-app/">Guide to the first Hurricane-based Application</a>
  </p>
</div> 

## Intro

Django was developed with the *batteries included*-approach and already handles most of the challenges around 
web development with grace. It was initially developed at a time when web applications got deployed and run on a server 
(physical or virtual). With its *pragmatic design* it enabled many developers to keep up with changing requirements, 
performance and maintenance work.  
However, service architectures have become quite popular for complex applications in the past few years. They provide
a modular style based on the philosophy of dividing overwhelming software projects into smaller and more controllable 
parts. The advantage of highly specialized applications gained prominence among developers, but introduces new 
challenges to the IT-operation.   
However, with the advent of Kubernetes and the cloud-native development philosophy a couple of new possibilities emerged
to run those service-based applications even better. Kubernetes is a wonderful answer for just as many IT-operation 
requirements as Django is for web development. The inherent monolithic design of Django can be tempting to roll out 
recurring operation patterns with each application. It's not about getting Django to run in a 
Kubernetes cluster (you may already solved this), it's about integrating Django as tightly as possible with Kubernetes 
in order to harness the full power of that platform. Creating the most robust, scalable and secure applications 
with Django by leveraging the existing expertise of our favorite framework is the main goal of this initiative.

Hurricane is supposed to make the most out of the existing Django ecosystem without reinventing the wheel. 
We will collect best-practices and opinions about how to run Django in Kubernetes and put them on Hurricane's roadmap.

### Application Server
Why another app server instead of *uwsgi*, *gunicorn* or *mod_wsgi*? We need a cloud-native app server which is
much more tidily coupled to the Django application itself. Think of special url routes for Kubernetes probes! Building a
special View in each and every Django application is not an appropriate solution. What about the Kubernetes Metrics API?
That's all something we **don't** want to take care of in our Django code.  
Those traditional app servers (i.e. uwsgi et.al.) have a highly optimized process model for bare-server deployments with
many CPUs, multiple threads and so on. In Kubernetes the scaling of an application is done through the Replication-value
in a workload description manifest. This is no longer something we configure with app server parameters.
  
## Installation

Hurricane can be installed from a Python Package Index:
```bash
pip3 install hurricane
```

Add *"hurricane"* to your *INSTALLED_APPS*: 
```python
INSTALLED_APPS += (
    'hurricane',
)
```
You can start the Hurricane server with a following command:
```python
python manage.py serve --autoreload --static
```
Ouput of this command looks as following:

```
System check identified some issues:

2022-05-04 02:19:07,521 INFO     hurricane.server.general Tornado-powered Django web server
2022-05-04 02:19:07,521 INFO     hurricane.server.general Starting probe application running on port 8001 with route liveness-probe: /alive, readiness-probe: /ready, startup-probe: /startup
2022-05-04 02:19:07,523 INFO     hurricane.server.general Starting HTTP Server on port 8000
2022-05-04 02:19:07,524 INFO     hurricane.server.general Startup time is 0.0026285648345947266 seconds
```

There are many options that can be used in a combination with the serve command. Please refer to the [documentation](https://django-hurricane.readthedocs.io/en/latest/usage.html) to learn more about the options.

Django-hurricane works best in combination with Kubernetes, as it includes the inbuilt health-probes, i.e. liveness, readiness and startup probes. Additionally, it is possible to implement custom checks. These checks will be executed after the standard django checks. Follow our guide to learn [how to write a custom check](https://django-hurricane.io/custom-checks/).


## Commercial Support
Hurricane is developed and maintained by [Blueshoe](https://www.blueshoe.de). 
If you need any help implementing with hurricane or you want to tell us about the use-case, how you use hurricane, please contact us: hurricane@blueshoe.de.