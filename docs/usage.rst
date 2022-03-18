User's guide
============

.. contents:: Table of Contents
   :depth: 4
   :local:

Introduction
------------
Hurricane is an initiative to fit `Django <https://www.djangoproject.com/>`_ perfectly with
`Kubernetes <https://kubernetes.io/>`_. It is supposed to cover many capabilities in order to run Django in a
cloud-native environment, including a `Tornado <https://www.tornadoweb.org/>`_-powered Django application server. It
was initially created by `Blueshoe GmbH <https://www.blueshoe.de/>`_.

Django was developed with the batteries included-approach and already handles most of the challenges around web
development with grace. It was initially developed at a time when web applications got deployed and run on a server
(physical or virtual). With its pragmatic design it enabled many developers to keep up with changing requirements,
performance and maintenance work. However, service architectures have become quite popular for complex applications
in the past few years. They provide a modular style based on the philosophy of dividing overwhelming software projects
into smaller and more controllable parts. The advantage of highly specialized applications gained prominence among
developers, but introduces new challenges to the IT-operation. However, with the advent of Kubernetes and the
cloud-native development philosophy a couple of new possibilities emerged to run those service-based applications even
better. Kubernetes is a wonderful answer for just as many IT-operation requirements as Django is for web development.
The inherent monolithic design of Django can be tempting to roll out recurring operation patterns with each application.
It's not about getting Django to run in a Kubernetes cluster (you may already solved this), it's about integrating
Django as tightly as possible with Kubernetes in order to harness the full power of that platform. Creating the most
robust, scalable and secure applications with Django by leveraging the existing expertise of our favorite framework is
the main goal of this initiative.

Using a Tornado-powered application server gives several advantages compared to the standard Django application server.
It is a single-threaded and at the same time a non-blocking server, that includes a builtin IO Loop from
`asyncio <https://docs.python.org/3/library/asyncio.html>`_ library. Django application server is blocked while waiting
for the client. On the other hand a Tornado application server can handle processes asynchronously and thus is not blocked
while waiting for the client or the database. This also gives the possibility to run webhooks and other asynchronous tasks
directly in the application server, avoiding the usage of external asynchronous task queues such as Celery.

Application Server
------------------

Run the application server
^^^^^^^^^^^^^^^^^^^^^^^^^^

In order to start the Django app run the management command *serve*:
::
   python manage.py serve

This command simply starts a Tornado-based application server ready to serve your Django application.
There is no need for any other application server.

Command options for *serve*-command:

+--------------------+-------------------------------------------------------------------------------------+
| **Option**         | **Description**                                                                     |
+--------------------+-------------------------------------------------------------------------------------+
| --static           | Serve collected static files                                                        |
+--------------------+-------------------------------------------------------------------------------------+
| --media            | Serve media files                                                                   |
+--------------------+-------------------------------------------------------------------------------------+
| --autoreload       | Reload code on change                                                               |
+--------------------+-------------------------------------------------------------------------------------+
| --debug            | Set Tornado's Debug flag (don't confuse with Django's DEBUG=True)                   |
+--------------------+-------------------------------------------------------------------------------------+
| --port             | The port for Tornado to listen on (default is port 8000)                            |
+--------------------+-------------------------------------------------------------------------------------+
| --startup-probe    | The exposed path (default is /startup) for probes to check startup                  |
+--------------------+-------------------------------------------------------------------------------------+
| --readiness-probe  | The exposed path (default is /ready) for probes to check readiness                  |
+--------------------+-------------------------------------------------------------------------------------+
| --liveness-probe   | The exposed path (default is /alive) for probes to check liveness                   |
+--------------------+-------------------------------------------------------------------------------------+
| --probe-port       | The port for Tornado probe routes to listen on (default is the next port of --port) |
+--------------------+-------------------------------------------------------------------------------------+
| --req-queue-len    | Threshold of queue length of request, which is considered for readiness probe,      |
|                    | default value is 10                                                                 |
+--------------------+-------------------------------------------------------------------------------------+
| --no-probe         | Disable probe endpoint                                                              |
+--------------------+-------------------------------------------------------------------------------------+
| --no-metrics       | Disable metrics collection                                                          |
+--------------------+-------------------------------------------------------------------------------------+
| --command          | Repetitive command for adding execution of management commands before serving       |
+--------------------+-------------------------------------------------------------------------------------+
| --check-migrations | Check if all migrations were applied before starting application                    |
+--------------------+-------------------------------------------------------------------------------------+
| --webhook-url      | If specified, webhooks will be sent to this url                                     |
+--------------------+-------------------------------------------------------------------------------------+
| --pycharm-host     | The host of the pycharm debug server                                                |
+--------------------+-------------------------------------------------------------------------------------+
| --pycharm-port     | The port of the pycharm debug server. This is only used in combination              |
|                    | with the '--pycharm-host' option                                                    |
+--------------------+-------------------------------------------------------------------------------------+

**Please note**: :code:`req-queue-len` parameter is set to a default value of 10. It means, that if the length of the
asynchronous tasks' queue will exceed 10, readiness probe will return the status 400 until the length of the queue
gets below the :code:`req-queue-len` value. Adjust this parameter if you want the asynchronous task queue to be larger
than 10.

Probes and the System Check Framework
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The probe endpoint invokes `Django system check framework <https://docs.djangoproject.com/en/2.2/topics/checks/>`_.
This endpoint is called in a certain intervals by Kubernetes, hence we get regular checks on the application. That's
a well-suited approach to integrate custom checks (please refer to the Django documentation how to do that) and get
health and sanity checks for free. Upon unhealthy declared applications (error-level) Kubernetes will restart the
application and remove the unhealthy PODs once a new instance is in a healthy state.
A port for the probe route is separated from the application's port. If the probe port is not specified, it
will be set to the application port plus one e.g. if the application port is 8000, the probe port will be set to 8001.
For more information about this topic on a Kubernetes side, please refer to
`Configure Liveness, Readiness and Startup Probes <https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/>`_.


Management commands
^^^^^^^^^^^^^^^^^^^
Management commands can be added as options for the hurricane serve command. Kubernetes is be able to poll startup probe
and if management commands are still running, it knows, that it should not restart the container yet. Management
commands can be given as repeating arguments to the serve management command e.g.:
::
    python manage.py serve --command makemigrations --command migrate

If you want to add some options to the specific management command take both this command and it's options in the
quotation marks:
::
    python manage.py serve --command "compilemessages --no-color"

**Important:** management commands should be given in the order, which is required for django application. Each
management command is then executed sequentially. Commands, which depend on other commands should be given after
the commands they depend on. E.g. management_command_2 is depending on management_command_1, thus the serve command
should look like this:
::
    python manage.py serve --command management_command_1 --command management_command_2

Endpoints
^^^^^^^^^

Probe server creates handlers for three endpoints: startup, readiness and liveness.

.. image:: _static/img/django-hurrican-flowchart-K8s-Probes.png
  :width: 600
  :alt: Alternative text

where **1** is a Kubernetes startup probe, it returns a response with a status 400, if the application has not started
yet or/and management commands are not finished yet. After finishing management commands and starting HTTP Server this
endpoint will return a response of status 200 and from that point, Kubernetes will know, that the application was
started, so readiness and liveness probes can be polled.
**2a** and **2b** are readiness and liveness probes respectively. Kubernetes will poll these probes, only after the
startup probe returns 200 for the first time. The readiness probe checks the length of the request queue, if it
is larger than the threshold, it returns 400, which means, that application is not ready for further requests.
The liveness probe uses Django system check framework to identify problems with the Django application.
**3** are api requests, sent by the application service, which are then handled in Django application.

Probe server, which defines handlers for every probe endpoint, runs in the main loop. Execution of management
commands does not block the main event loop and thus runs in a separate executor. Upon successful execution
of management commands, the HTTP server is started.

Webhooks
^^^^^^^^

Webhooks can be specified as command options of *serve*-command. Right now, there are available two webhooks: startup-
webhook and liveness-webhook. First is an indicator of the status of startup probe. Startup-webhook sends a status, and
depending on success or failure of startup process it can send either positive or negative status. Liveness-webhook is
triggered, when liveness-webhook url is specified and the liveness-probe is requested and the change of the health
state is detected. For instance, if liveness probe is requested, but there was no change of the health variable, no
webhook will be sent. Similarly, readiness webhook is sent upon the change of it's state variable.
Webhooks run as asynchronous processes and thus do not block the asyncio-loop. If the specified url is wrong or it
cannot handle webhook properly, an error or a warning will be logged. Response of the webhook should
be 200 to indicate the success of receiving webhook.

**Creating new webhook types**
The new webhook types can be specified in an easy manner in the hurricane/webhooks/webhook_types.py file. They need to
specify Webhook class as a parent class. After creating a new webhook class, you can specify a new argument of the
management command to parametrize the url, to which webhook will be sent. Then, you can just create an object of webhook
and run it at the place in code, where it should be executed. Run method should have several methods i.e. url (to which
webhook should be sent) and status (webhook on success or failure).

Check migrations
^^^^^^^^^^^^^^^^

When check-migrations option is enabled, hurricane checks if database is available and subsequently checks if there are
any unapplied migrations. It is executed in a separate thread, so the main thread with the probe server is not blocked.

Settings
^^^^^^^^
:code:`HURRICANE_VERSION` - is sent together with webhooks to distinguish between different versions.

Logging
^^^^^^^

It should be ensured, that the *hurricane* logger is added to Django logging configuration, otherwise log outputs will
not be displayed when application server will be started. Log level can be easily adjusted to own needs.

Example:
.. code-block:: python

   LOGGING = {
       "version": 1,
       "disable_existing_loggers": True,
       "formatters": {"console":
                        {"format": "%(asctime)s %(levelname)-8s %(name)-12s %(message)s"}
                     },
       "handlers": {
           "console": {
               "class": "logging.StreamHandler",
               "formatter": "console",
               "stream": sys.stdout,
           }
       },
       "root": {"handlers": ["console"], "level": "INFO"},
       "loggers": {
           "hurricane": {
               "handlers": ["console"],
               "level": os.getenv("HURRICANE_LOG_LEVEL", "INFO"),
               "propagate": False,
           },
       },
   }


AMQP Worker
-----------

Run the AMQP (0-9-1) Consumer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In order to start the Django-powered AMQP consumer following *consume*-command can be used:
::
    python manage.py consume HANDLER

This command starts a `Pika-based <https://pika.readthedocs.io/en/stable/>`_ amqp consumer which is observed by
Kubernetes. The required *Handler* argument is the dotted path to an *_AMQPConsumer* implementation. Please use
the *TopicHandler* as base class for your handler implementation as it is the only supported exchange type at the moment.
It's primarily required to implement the *on_message(...)* method to handle incoming amqp messages.

In order to establish a connection to the broker you case use one of the following options:
Load from *Django Settings* or *environment variables*:

+----------------+-------------------------------------------------------------------------------------+
| **Variable**   | **Help**                                                                            |
+----------------+-------------------------------------------------------------------------------------+
| AMQP_HOST      | amqp broker host                                                                    |
+----------------+-------------------------------------------------------------------------------------+
| AMQP_PORT      | amqp broker port                                                                    |
+----------------+-------------------------------------------------------------------------------------+
| AMQP_VHOST     | virtual host (defaults to "/")                                                      |
+----------------+-------------------------------------------------------------------------------------+
| AMQP_USER      | username for broker connection                                                      |
+----------------+-------------------------------------------------------------------------------------+
| AMQP_PASSWORD  | password for broker connection                                                      |
+----------------+-------------------------------------------------------------------------------------+


The precedence is: 1. command line option (if available), 2. Django settings, 3. environment variable

Command options for *consume*-command:

+------------------+-------------------------------------------------------------------------------------+
| **Option**       | **Description**                                                                     |
+------------------+-------------------------------------------------------------------------------------+
| --queue          | The queue name this consumer declares and binds to                                  |
+------------------+-------------------------------------------------------------------------------------+
| --exchange       | The exchange name this consumer declares                                            |
+------------------+-------------------------------------------------------------------------------------+
| --amqp-port      | The broker service port                                                             |
+------------------+-------------------------------------------------------------------------------------+
| --amqp-host      | The broker host name in the cluster                                                 |
+------------------+-------------------------------------------------------------------------------------+
| --amqp-vhost     | The consumer's virtual host to use                                                  |
+------------------+-------------------------------------------------------------------------------------+
| --handler        | the Hurricane AMQP handler class (dotted path)                                      |
+------------------+-------------------------------------------------------------------------------------+
| --startup-probe  | The exposed path (default is /startup) for probes to check startup                  |
+------------------+-------------------------------------------------------------------------------------+
| --req-queue-len  | Threshold of queue length of request, which is considered for readiness probe,      |
|                  | default value is 10                                                                 |
+------------------+-------------------------------------------------------------------------------------+
| --liveness-probe | The exposed path (default is /alive) for probes to check liveness                   |
+------------------+-------------------------------------------------------------------------------------+
| --probe-port     | The port for Tornado probe routes to listen on (default is the next port of --port) |
+------------------+-------------------------------------------------------------------------------------+
| --req-queue-len  | Threshold of queue length of request, which is considered for readiness probe       |
+------------------+-------------------------------------------------------------------------------------+
| --no-probe       | Disable probe endpoint                                                              |
+------------------+-------------------------------------------------------------------------------------+
| --no-metrics     | Disable metrics collection                                                          |
+------------------+-------------------------------------------------------------------------------------+
| --autoreload     | Reload code on change                                                               |
+------------------+-------------------------------------------------------------------------------------+
| --debug          | Set Tornado's Debug flag (don't confuse with Django's DEBUG=True)                   |
+------------------+-------------------------------------------------------------------------------------+
| --reconnect      | Reconnect the consumer if the broker connection is lost (not recommended)           |
+------------------+-------------------------------------------------------------------------------------+

**Please note**: :code:`req-queue-len` parameter is set to a default value of 10. It means, that if the length of
asynchronous tasks queue will exceed 10, readiness probe will return status 400 until the length of tasks gets below the
:code:`req-queue-len` value. Adjust this parameter if you want asynchronous task queue to be larger than 10.

Example AMQP Consumer
^^^^^^^^^^^^^^^^^^^^^

Implementation of a basic AMQP handler with no functionality:

.. code-block:: python
   :emphasize-lines: 3,5

   # file: myamqp/consumer.py
   from hurricane.amqp.basehandler import TopicHandler

   class MyTestHandler(TopicHandler):
        def on_message(self, _unused_channel, basic_deliver, properties, body):
             print(body.decode("utf-8"))
             self.acknowledge_message(basic_deliver.delivery_tag)

This handler can be started using the following command:
::
    python manage.py consume myamqp.consumer.MyTestHandler --queue my.test.topic --exchange test --amqp-host 127.0.0.1 --amqp-port 5672

Test Hurricane
--------------

In order to run the entire test suite following commands should be executed:
::
   shell
   pip install -r requirements.txt
   coverage run manage.py test
   coverage combine
   coverage report

**Important:** the AMQP testcase requires *Docker* to be accessible from the current user as it
spins up a container with *RabbitMQ*. The AMQP consumer in a test mode will connect to
it and exchange messages using the *TestPublisher* class.

Debugging django applications
-----------------------------
Debugging a python/django or in fact any application running in a kubernetes cluster can be cumbersome. Some of the most
common IDEs use different approaches to remote debugging:

1. The `Microsoft Debug Adapter Protocol (DAP) <https://microsoft.github.io/debug-adapter-protocol/>`_ is used, among
   others, by Visual Studio Code and Eclipse.
   A full list of supporting IDE's can be found `here <https://microsoft.github.io/debug-adapter-protocol/implementors/tools/>`_.
   Here, the application itself must listen on a port and wait for the debug client (in this case: the IDE's debug UI)
   to connect.
2. Pycharm, which uses the `pydevd <https://github.com/fabioz/PyDev.Debugger>`_ debugger, sets up a debug server (you will have to configure a host
   and a port in your IDE debug run config) and waits for the application to connect. Therefore, the application must
   know where to reach the debug server.

Both approaches would usually require the application to contain code that is specific to the IDE/protocol used by the
developer. Django-hurricane supports these two approaches without the need for changes to your django project:

1. For the Debug Adapter Protocol (Visual Studio Code, Eclipse, ...)

   * a. Install Djanog-hurricane with the "debug" option: :code:`pip install django-hurricane[debug]`.

   * b. Run it with the "--debugger" flag, e.g.: :code:`python manage.py serve --debugger`.

   * c. Optionally, provide a port (default: 5678), e.g.: :code:`python manage.py serve --debugger --debugger-port 1234`.
Now you can connect your IDE's remote debug client (configure the appropriate host and port).

2. For working with the Pycharm debugger:

   * a. Install Djanog-hurricane with the "pycharm" option: :code:`pip install django-hurricane[pycharm]`.

   * b. Configure the remote debug server in Pycharm and start it.

   * c. Run your app with the "--pycharm-host" and "--pycharm-port" flags, e.g.: :code:`python manage.py serve --pycharm-host 127.0.0.1 --pycharm-port 1234`.

Now the app should connect to the debug server. Upon connection, the execution will halt. You must resume it from Pycharm's debugger UI.

For both approaches, you may have to configure path mappings in your IDE that map your local source code directories to
the corresponding locations inside the running container (e.g. "/home/me/proj/src" -> "/app").