![Hurricane Logo](https://raw.githubusercontent.com/Blueshoe/django-hurricane/master/docs/_static/img/logo.png)

--------------------------------------------------------------------------------
[![PyPI version](https://badge.fury.io/py/django-hurricane.svg)](https://badge.fury.io/py/django-hurricane)
[![Build Status](https://travis-ci.org/Blueshoe/django-hurricane.svg?branch=master)](https://travis-ci.org/Blueshoe/django-hurricane)
[![Coverage Status](https://coveralls.io/repos/github/Blueshoe/django-hurricane/badge.svg)](https://coveralls.io/github/Blueshoe/django-hurricane)
[![ReadTheDocs](https://readthedocs.org/projects/django-hurricane/badge/?version=latest)](https://django-hurricane.readthedocs.io/en/latest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Hurricane is an initiative to fit Django perfectly with Kubernetes. It is supposed to cover
many capabilities in order to run Django in a cloud-native environment, including a Tornado-powered Django app server.  


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
- [ ] actual Tornado integration (currently uses the `tornado.wsgi.WSGIContainer`)
- [ ] web sockets with Django 3
- [ ] Testing, testing in production
- [ ] Load-testing, automated performance regression testing  
- [ ] Implement the Kubernetes Metrics API
- [ ] Different endpoints for all Kubernetes probes
- [ ] Implement hooks for calling webservices (e.g. for deployment or health state changes) 
- [ ] Add another metrics collector endpoint (e.g Prometheus)  


### Celery
In the future, Hurricane provides a sophisticated Django-celery integration with health checks and Kubernetes-scaling.

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

Hurricane is currently available only on Blueshoe's Python Package Index.
```bash
pip3 install hurricane
```

Add *"hurricane"* to your *INSTALLED_APPS*: 
```python
INSTALLED_APPS += (
    'hurricane',
)
```

## Usage

### Application Server

#### Run the application server

In order to start the Django app run the management command *serve*:  

```bash
python manage.py serve
```
It simply starts a Tornado-based application server ready to serve your Django application. No need for any other 
app server.

There are a couple of command options:  

| Option         | Help  |   
| :----          | :---  |   
| --static       | Serve collected static files |  
| --media        | Serve media files |  
| --autoreload   | Reload code on change |  
| --debug        | Set Tornado's Debug flag (don't confuse with Django's DEBUG=True) |  
| --port         | The port for Tornado to listen on (default is port 8000) |  
| --probe        | The exposed path (default is /alive) for probes to check liveness and readyness |
| --probe-port   | The port for Tornado probe routes to listen on (default is the next port of --port) |  
| --no-probe     | Disable probe endpoint |  

#### Probes and the System Check Framework

The probe endpoint invokes Django's check framework (please see: https://docs.djangoproject.com/en/2.2/topics/checks/). 
This endpoint is called in a certain interval by Kubernetes, hence we get regular checks on the application. That's 
a well-suited approach to integrate custom checks (please refer to the Django documentation how to do that) and get 
health and sanity checks for free. Upon unhealthy declared applications (error-level) Kubernetes will restart the 
application and remove unhealthy PODs once a new instance is in healthy state.  
The port for the probe route is separated from the application's port. If not specified, the probe port is one port
added to the application's port.

#### Logging
Be sure to add the *hurricane* logger to your Django logging configuration otherwise you won't see any output
the moment you started the application server. Feel free to adjust the log level according to your needs.

### AMQP Worker

#### Run the AMQP (0-9-1) Consumer

In order to start the Django-powered AMQP consumer run the management command *consume*:  

```bash
python manage.py consume HANLDER 
```
This command starts a [Pika-based](https://pika.readthedocs.io/en/stable/) amqp consumer which is observed by
Kubernetes. The required *Handler* argument is the dotted path to an *_AMQPConsumer* implementation. Please use
the *TopicHandler* as base class for your handler implementation as it is the only supported exchange type at the moment.
It's primarily required to implement the *on_message(...)* method to handle incoming amqp messages.

In order to establish a connection to the broker you case use one of the folloging options:  
Load from *Django Settings* or *environment variables*:  

| Variable  | Help |  
| :----     | :---  |  
| AMQP_HOST | amqp broker host |
| AMQP_PORT | amqp broker port |  
|AMQP_VHOST | virtual host (defaults to "/") |  
|AMQP_USER | username for broker connection |  
|AMQP_PASSWORD | password for broker connection |   

The precedence is: 1. command line option (if available), 2. django settings, 3. environment variable

There are a couple of command options:  

| Option         | Help  |   
| :----          | :---  |
| --queue        | The queue name this consumer declares and binds to |  
| --exchange     | The exchange name this consumer declares |  
| --amqp-host    | The broker host name in the cluster |  
| --amqp-port    | The broker service port |  
| --amqp-vhost   | The consumer's virtual host to use  |  
| --reconnect    | Reconnect the consumer if the broker connection is lost (not recommended) |  
| --autoreload   | Reload code on change |  
| --debug        | Set Tornado's Debug flag (don't confuse with Django's DEBUG=True) |
| --probe        | The exposed path (default is /alive) for probes to check liveness and readyness |
| --probe-port   | The port for Tornado probe routes to listen on (default is the next port of --port) |  
| --no-probe     | Disable probe endpoint |  


#### Example AMQP Consumer

Please see this example implementation of a useless AMQP handler:
```python
# file: myamqp/consumer.py
from hurricane.amqp.basehandler import TopicHandler


class MyTestHandler(TopicHandler):
    def on_message(self, _unused_channel, basic_deliver, properties, body):
        print(body.decode("utf-8"))
        self.acknowledge_message(basic_deliver.delivery_tag)
```

This handler is started using the following command:
```bash
python manage.py consume myamqp.consumer.MyTestHandler --queue my.test.topic --exchange test \ 
--amqp-host 127.0.0.1 --amqp-port 5672
```


## Test Hurricane

In order to run the entire test suite do:
```shell
pip install -r requirements.txt
coverage run manage.py test
coverage combine
coverage report
```
**Important:** the AMQP testcase requires *Docker* to be accessible from your current user as it 
spins up a container with *RabbitMQ*. The AMQP consumer under test will connect to
it and exchange messages using the *TestPublisher* class.
