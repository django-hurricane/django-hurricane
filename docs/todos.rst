Todos
=====

**Application server**

- [x] Basic setup, POC, logging
- [ ] actual Tornado integration (currently uses the `tornado.wsgi.WSGIContainer`)
- [ ] web sockets with Django 3
- [ ] Testing, testing in production
- [ ] Load-testing, automated performance regression testing
- [ ] Implement the Kubernetes Metrics API
- [ ] Different endpoints for all Kubernetes probes
- [ ] Implement hooks for calling webservices (e.g. for deployment or health state changes)
- [ ] Add another metrics collector endpoint (e.g Prometheus)

**Celery**

- [ ] Concept draft
- [ ] Kubernetes health probes for celery workers
- [ ] Kubernetes health probes for celery beat
- [ ] Implement hooks for calling webservices (e.g. for deployment or health state changes)
- [ ] Implement the Kubernetes Metrics API

**AMQP**

- [x] Concept draft
- [ ] Kubernetes health probes for amqp workers
- [ ] Implement hooks for calling webservices (e.g. for deployment or health state changes)
- [ ] Implement the Kubernetes Metrics API

**Guidelines**

- [ ] Concept draft
- [ ] Cookiecutter template
- [ ] Container (Docker) best-practices