![Hurricane Logo](https://raw.githubusercontent.com/Blueshoe/django-hurricane/master/docs/_static/img/logo.png)

--------------------------------------------------------------------------------
[![PyPI version](https://badge.fury.io/py/django-hurricane.svg)](https://badge.fury.io/py/django-hurricane)
![Build Status](https://github.com/Blueshoe/django-hurricane/actions/workflows/python-app.yml/badge.svg)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Blueshoe_django-hurricane&metric=alert_status)](https://sonarcloud.io/dashboard?id=django-hurricane_django-hurricane)
[![Coverage Status](https://coveralls.io/repos/github/django-hurricane/django-hurricane/badge.svg?branch=main)](https://coveralls.io/github/django-hurricane/django-hurricane?branch=main)
[![ReadTheDocs](https://readthedocs.org/projects/django-hurricane/badge/?version=latest)](https://django-hurricane.readthedocs.io/en/latest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Hurricane is an initiative to fit Django perfectly with Kubernetes. It is supposed to cover
many capabilities in order to run Django in a cloud-native environment, including a Tornado-powered Django app server.  

## Documentation

You can find the full documentation [here](https://django-hurricane.readthedocs.io/en/latest/).

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

## Parts
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
  
**Todo**

- [x] Basic setup, POC, logging
- [x] Different endpoints for all Kubernetes probes
- [x] Extensive documentation
- [x] Django management command execution before serving
- [ ] actual Tornado integration (currently uses the `tornado.wsgi.WSGIContainer`)
- [ ] web sockets with Django 3
- [ ] Testing, testing in production
- [ ] Load-testing, automated performance regression testing  
- [ ] Implement the Kubernetes Metrics API
- [x] Implement hooks for calling webservices (e.g. for deployment or health state changes) 
- [ ] Add another metrics collector endpoint (e.g Prometheus)  


### Celery
In the future, Hurricane should provide a sophisticated Django-celery integration with health checks and Kubernetes-scaling.

**Todo**

- [ ] Concept draft
- [ ] Kubernetes health probes for celery workers
- [ ] Kubernetes health probes for celery beat
- [ ] Implement hooks for calling webservices (e.g. for deployment or health state changes) 
- [ ] Implement the Kubernetes Metrics API


### AMQP Worker/Consumer
Hurricane provides a generic yet simple *amqp* worker with health checks and Kubernetes-scaling.

**Todo**

- [x] Concept draft
- [ ] Kubernetes health probes for amqp workers
- [ ] Implement hooks for calling webservices (e.g. for deployment or health state changes) 
- [ ] Implement the Kubernetes Metrics API

### Guidelines
In order to keep Django as lean and swift as possible we have to get rid of several parts: unneeded middlewares,
apps and other overhead. A small Django-based service does not need all the batteries Django comes with. In many
cases the superb ORM (object relation mapper) and a simple HTTP-interface is all it needs.

**Todo**

- [ ] Concept draft
- [ ] Cookiecutter template
- [ ] Container (Docker) best-practices



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

Check out the [documentation](https://django-hurricane.readthedocs.io/en/latest/) for more information and a user's guide.

## Commercial Support
Hurricane is developed and maintained by [Blueshoe](https://www.blueshoe.de). 
If you need any help implementing with hurricane, please contact us: hurricane@blueshoe.de.

## Docs
To build the docs the following command should be executed in the docs directory:
```bash
make html
```
