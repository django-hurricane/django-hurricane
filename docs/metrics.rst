Metrics
=======

Hurricane comes with a small framework to collect and expose metrics about your application.

Builtin Metrics
---------------
Hurricane provides a few builtin metrics:
    - request queue length
    - overall request count
    - average response time
    - startup time metric

These metrics are collected from application start until application end. Keep in mind that these metrics do not
exactly represent the current state of the application - rather the current state since the start of the process.
Startup time metric is used for startup probe. It is set after all management commands were finished and HTTP server
was started.


Custom Metrics
--------------
It is possible to define new custom metrics. The new metric class can inherit from StoredMetric class, which defines
methods for saving metric value into the registry and for value retrieval from the registry. It should include code
variable, which is used as a key for storing and retrieving value from the registry dictionary. Custom metric should be
also registered in a metric registry. This can be done by adding the following lines to init file of metrics package:
::
    # file: metrics/__init__.py
    from hurricane.metrics.requests import <CustomMetricClass>

    registry.register(<CustomMetricClass>)


Disable Metrics
---------------
If you'd like to disable the metric collection use the `--no-metrics` flag with the serve command:
::
    python manage.py serve --no-metrics
