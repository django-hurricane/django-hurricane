Metrics
=======

Hurricane comes with a small framework to collect and expose metrics about your application.

Builtin Metrics
---------------
Hurricane provides a few builtin metrics:
    - request queue length
    - overall request count
    - average response time

These metrics are collected from application start until application end. Keep in mind that these metrics do not
exactly represent the current state of the application - rather the current state since the start of the process.


Custom Metrics
--------------
# TODO


Disable Metrics
---------------
If you'd like to disable the metric collection use the `--no-metrics` flag with the serve command:
::
    python manage.py serve --no-metrics

