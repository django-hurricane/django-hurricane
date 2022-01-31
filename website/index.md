---
layout: page
title: Kubernetes-supercharged Django Applications
subtitle: A Kubernetes Native Stack Specifically Created For Django
cover-img: assets/img/bg_clouds1.png
---

<div class="jumbotron dh-color">
    <p class="lead">Hurricane is an initiative to fit Django perfectly with Kubernetes. It is supposed to cover many capabilities in order to run Django in a Cloud Native environment, including a Tornado-powered Django app server.</p>
    <h2>Now available <a href="https://github.com/Blueshoe/django-hurricane/releases/tag/0.9.2">Hurricane 0.9.2</a></h2>
    <hr class="my-4">
    <div class="centered">
        <a class="btn btn-success btn-lg" href="getting-started">Get Started With Hurricane</a>
    </div>
</div>



[![PyPI version](https://badge.fury.io/py/django-hurricane.svg)](https://badge.fury.io/py/django-hurricane)
![Build Status](https://github.com/Blueshoe/django-hurricane/actions/workflows/python-app.yml/badge.svg)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Blueshoe_django-hurricane&metric=alert_status)](https://sonarcloud.io/dashboard?id=Blueshoe_django-hurricane)
[![Coverage Status](https://coveralls.io/repos/github/Blueshoe/django-hurricane/badge.svg)](https://coveralls.io/github/Blueshoe/django-hurricane)
[![ReadTheDocs](https://readthedocs.org/projects/django-hurricane/badge/?version=latest)](https://django-hurricane.readthedocs.io/en/latest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Key Features of Django Hurricane

The goal of Django Hurricane is to build the most robust and scalable applications with Django by leveraging the existing know-how of our favourite framework.

-   Better integration of Django and Kubernetes
-   Tornado-powered Django application server
-   Tornado-powered Django AMQP consumer
-   Probe server out-of-the box with options for standard Kubernetes probes
-   Webhooks to check up on the application status

## Why Hurricane?
Django was developed with the batteries included approach and already handles most of the challenges around web 
development with grace. It was initially developed at a time when web applications got deployed and run on a server 
(physical or virtual). Its pragmatic design enabled many developers to keep up with changing requirements, 
performance and maintenance work.  
<br />
However, service architectures have become quite popular for complex applications in the past few years. They provide a 
modular style based on the philosophy of dividing overwhelming software projects into smaller and more controllable 
parts. The advantage of highly specialized applications gained prominence among developers but introduces new 
challenges to the IT operation.
<br />

However, with the advent of Kubernetes and the Cloud Native development philosophy, a couple of new possibilities 
emerged to run those service-based applications even better. Kubernetes is a wonderful answer for just as many 
IT operation requirements as Django is for web development. The inherent monolithic design of Django can be tempting 
to roll out recurring operation patterns with each application. It's not about getting Django to run in a 
Kubernetes cluster (you may have already solved this), it's about integrating Django as tightly as possible with Kubernetes 
in order to harness the full power of that platform. Creating the most robust, scalable and secure applications with 
Django by leveraging the existing expertise of our favourite framework is the main goal of this initiative.
