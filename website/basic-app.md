---
layout: page
title: Guide to your first Hurricane-based Application
---
## What you'll learn
- Create a Django app with Hurricane
- Run it locally and then in Kubernetes with k3d
- Add a custom check for Hurricane

## Table of contents:
1. [Create basic Django application](#1-create-basic-django-application)
   1. [Manual Django setup](#manual-django-setup)
   2. [Setup with a cookiecutter template](#setup-with-a-cookiecutter-template)
   3. [Basic setup of the spacecrafts application](#basic-setup-of-the-spacecrafts-application)
   4. [Configure GraphQL](#configure-graphql)
   5. [Start hurricane server](#start-hurricane-server)
2. [Run this application using Django-Hurricane in a Kubernetes cluster](#2-run-this-application-using-django-hurricane-in-a-kubernetes-cluster)
   1. [Built-in Kubernetes probes and custom check handler](#built-in-kubernetes-probes-and-custom-check-handler)
   2. [Local Kubernetes development: code hot-reloading, debugging and more](#local-kubernetes-development-code-hot-reloading-debugging-and-more)

## 1. Create basic Django application
We will make it a little bit more interesting and instead of a plain Django application we will create a django-graphene application.
You can learn more about Graphene [<ins>**here**</ins>](https://docs.graphene-python.org/projects/django/en/latest/). In it's essence, with 
django-graphene we will be able to use GraphQL functionality for our application.

> Alternatively, you can skip this part and clone [<ins>**this repository**</ins>](https://github.com/django-hurricane/spacecrafts-demo). 
> 
> You can then head directly to step 2:  
> [<ins>**Run this application using Django Hurricane**</ins>](#2-run-this-application-using-django-hurricane)

If you want to setup the project manual, you can proceed with the following section.
Alternatively you could [<ins>**head to the next section**</ins>](#setup-with-a-cookiecutter-template) which uses the [<ins>**cookiecutter template**</ins>](https://github.com/Blueshoe/django-hurricane-template) we developed to bootstrap Django applications that use Django-Hurricane.
Keep in mind that the cookiecutter template includes more (e.g. poetry, pre-commit, GitHub workflow, split-settings, etc.), so you might have slightly different results when doing the manual setup. 

### Manual Django setup
First, create a project directory
~~~bash
mkdir spacecrafts
cd spacecrafts
~~~

Create a virtualenv to isolate our package dependencies locally
~~~bash
virtualenv env
source env/bin/activate  # On Windows use `env\Scripts\activate`
~~~

Install Django, Django-Graphene and Django-Hurricane
~~~bash
pip install django~=3.2.12 graphene_django django-hurricane
~~~

Create directory to contain source code. This step is optional, we do it so it matches our cookiecutter and [<ins>**our repository**</ins>](https://github.com/django-hurricane/spacecrafts-demo).
~~~bash
mkdir src
cd src
~~~

Set up a new project
~~~bash
django-admin startproject spacecrafts .  # Note:'.' character
~~~

Create a directory to contain Django apps. This is also optional and done to match the cookiecutter.
~~~bash
mkdir apps
~~~

### Setup with a cookiecutter template

If necessary [<ins>**install cookiecutter**</ins>](https://cookiecutter.readthedocs.io/en/1.7.2/installation.html) (i.e. `pip install cookiecutter`).

Use our cookiecutter template to set up the Django project
~~~bash
cookiecutter gh:Blueshoe/django-hurricane-template
~~~

You can use following answers for the prompt:
~~~bash
project_name [awesome-django-project]: spacecrafts
project_verbose_name [Awesome Django Hurricane Project]: A demo project to create "spacecrafts", using Django-Hurricane.
project_domain [blueshoe.de]: 
organization [Blueshoe GmbH]:
~~~

Create a virtualenv:
~~~bash
cd spacecrafts
virtualenv env
source env/bin/activate  # On Windows use `env\Scripts\activate`
~~~

If you know how to use [<ins>**poetry**</ins>](https://python-poetry.org/docs/), you can use it to add Django-Graphene and Django-Hurricane:
~~~bash
poetry add graphene-django django-hurricane
~~~
Otherwise you can just use pip
~~~bash
pip install graphene-django django-hurricane
~~~
In order to locally install the dependencies, you need to add following to `pyproject.toml`, for example directly under `authors = [...]`:
~~~bash
packages = [
    { include = "src" },
]
~~~
Install the rest of the dependencies (which are specified in `src/pyproject.toml`):
~~~bash
pip install .
~~~

The cookiecutter also includes [<ins>**django-csp**</ins>](https://django-csp.readthedocs.io/en/latest/), which is out of the scope of this tutorial.
If you know what you're doing, feel free to configure it correctly.
But you can just remove it from the project, by removing it from `_base_settings` in `src/configuration/__init__.py` and from `MIDDLEWARES` in `src/configuration/components/middlewares.py`.

To continue with the next section, change into the `src` directory
~~~bash
cd src
~~~

### Basic setup of the spacecrafts application
The following steps will create the spacecrafts application. They are the same, no matter whether you did a manual project setup or whether you used our cookiecutter template. 

Set up the application
~~~bash
cd apps
django-admin startapp components
cd ..
~~~

Create model structures
~~~python
# src/apps/components/models.py

from django.db import models


class Category(models.Model):
    title = models.CharField(
        max_length=100, 
    )

    def __str__(self):
        return self.title


class Component(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    category = models.ForeignKey(
        Category, 
        related_name="categories", 
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return self.title

~~~

Add your new app as well as `graphene_django` and `hurricane` to your settings file
~~~python
# manual setup: src/spacecrafts/settings.py 
# cookiecutter: src/configuration/components/apps.py

INSTALLED_APPS = [
    ...,
    "apps.components.apps.ComponentsConfig",
    "graphene_django",
    "hurricane",
]
~~~

To have hurricanes logs available, add the following logging setting to your settings file:
~~~python
# manual setup: src/spacecrafts/settings.py
# cookiecutter: src/configuration/components/logging.py

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {"console": {"format": "%(asctime)s %(levelname)-8s %(name)-12s %(message)s"}},
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

~~~

We also need to adapt the name of the app config:
~~~python
# src/apps/components/apps.py

from django.apps import AppConfig


class ComponentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.components'

~~~

Migrate changes
~~~bash
python manage.py makemigrations
python manage.py migrate
~~~

Our repository contains a fixture in `src/apps/components/fixture.yaml`, you can download it from [<ins>**here**</ins>](https://github.com/django-hurricane/spacecrafts-demo/blob/1ec41396048baef501092ebf247b5d7450bed515/src/apps/components/fixtures/components.json). It allows you to load data to your database from the fixture file, that defines several model instances
~~~bash
python manage.py loaddata components
~~~
Alternatively you can create model instances on your own through the admin interface. For that you need to add following lines to your admin file:

~~~python
# src/apps/components/admin.py

from django.contrib import admin
from apps.components.models import Category, Component

admin.site.register(Category)
admin.site.register(Component)

~~~

### Configure GraphQL

The essential part of `graphene_django` is a graph representation of objects. To create such a representation you need to create a so-called schema. Create a `schema.py` file in your projects root with the following content:

~~~python
# manual setup: src/spacecrafts/schema.py
# cookiecutter: src/configuration/schema.py

import graphene
from graphene_django import DjangoObjectType

from apps.components.models import Category, Component


class CategoryType(DjangoObjectType):
    class Meta:
        model = Category
        fields = ("id", "title")


class ComponentType(DjangoObjectType):
    class Meta:
        model = Component
        fields = ("id", "title", "description", "category")


class Query(graphene.ObjectType):
    all_components = graphene.List(ComponentType)
    category_by_name = graphene.Field(CategoryType, name=graphene.String(required=True))

    def resolve_all_components(root, info):
        return Component.objects.select_related("category").all()

    def resolve_category_by_name(root, info, name):
        try:
            return Category.objects.get(name=name)
        except Category.DoesNotExist:
            return None


schema = graphene.Schema(query=Query)

~~~
> For more information on the concept of schema, please refer to [<ins>**Graphene Documentation**</ins>](https://docs.graphene-python.org/projects/django/en/latest/schema/).

Now you just need to let Django know where it can find the graphene schema. Add following setting to your settings file:
If you did the manual Django setup:
~~~python
# src/spacecrafts/settings.py

GRAPHENE = {
    "SCHEMA": "spacecrafts.schema.schema"
}
~~~
If you did the cookiecutter setup (to keep it clean you can add a new file `src/configuration/components/graphene.py` for this and include it in the `_base_settings` specified in `src/configuration/__init__.py`):
~~~python
# src/configuration/components/commons.py

GRAPHENE = {
    "SCHEMA": "configuration.schema.schema"
}
~~~


You also need to add a graphql endpoint to your urls configuration. Your `urls.py` should look like the following:
~~~python
# manual setup: src/spacecrafts/urls.py
# cookiecutter: src/configuration/urls.py

from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from graphene_django.views import GraphQLView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("graphql", csrf_exempt(GraphQLView.as_view(graphiql=True))),
]
~~~

### Set environment variables

You need to set some environment variables, you can do that by creating a `.env`-file in `src` with following content:
~~~bash
# src/.env
DATABASE_ENGINE=django.db.backends.sqlite3
DATABASE_NAME=spacecrafts.sqlite3
DJANGO_SECRET_KEY=H96HwkhWFCKmWjRnJKJNkT3wSDCJ7MJ22Qi5C5t9UX8Hem89Q4
DJANGO_STATIC_ROOT=static
DJANGO_DEBUG=True
~~~

### Start hurricane server

Now you can start the server. With `--autoreload` flag server will be automatically reloaded upon changes in the code. 
Static files will be served if you add `--static` flag. We instruct hurricane to run two Django management command. We collect statics with `--command 'collectstatic --noinput'` and we also migrate the database with `--command 'migrate'`.
~~~bash
python manage.py serve --autoreload --static --command 'collectstatic --noinput' --command 'migrate'
~~~

You should get similar output upon the start of the server:
~~~bash
2022-01-21 10:19:21,434 INFO     hurricane.server.general Tornado-powered Django web server
2022-01-21 10:19:21,435 INFO     hurricane.server.general Autoreload was performed
2022-01-21 10:19:21,435 INFO     hurricane.server.general Starting probe application running on port 8001 with route liveness-probe: /alive, readiness-probe: /ready, startup-probe: /startup
[...]
2022-01-21 10:19:21,436 INFO     hurricane.server.general Starting HTTP Server on port 8000
2022-01-21 10:19:21,436 INFO     hurricane.server.general Serving static files under /static/ from static
2022-01-21 10:19:21,437 INFO     hurricane.server.general Startup time is 0.0026073455810546875 seconds
~~~

After going to the graphql url ([http://127.0.0.1:8000/graphql](http://127.0.0.1:8000/graphql)) you can play around with GraphQL querying. For example you could list all components and their categories:
~~~
{
  allComponents {
    id
    title
    description
    category {
      id
      title
    }
  }
}
~~~


In addition to the previously defined `admin` and `graphql` endpoints, hurricane starts a probe server on port+1, unless an explicit port for probes is specified. This feature is essential for cloud-native development, and it is only one of the many features of Django-Hurricane. For further features and information on hurricane, please refer to [<ins>**Full Django Hurricane Documentation**</ins>](https://django-hurricane.readthedocs.io/en/latest/).


## 2. Run this application using Django-Hurricane in a Kubernetes cluster

We're using [k3d](https://k3d.io/) to create and run a local kubernetes cluster. You can install it via:
~~~bash
wget -q -O - https://raw.githubusercontent.com/rancher/k3d/main/install.sh | bash
~~~

After installing k3d you can create a spacecrafts cluster with the following command:

~~~bash
k3d cluster create spacecrafts --agents 1 -p 8080:80@agent[0] 
~~~

Next thing, we need to build a docker image and push it to a registry. You can skip this step if you want and use the image from our public quay.io: [quay.io/django-hurricane/spacecrafts-demo](https://quay.io/repository/django-hurricane/spacecrafts-demo).
Remember to remove the adaptation of `pyproject.toml` if you've followed the project setup with our cookiecutter.

Now we need to install helm charts, which will define our cluster infrastructure. [<ins>**Our repository**</ins>](https://github.com/django-hurricane/spacecrafts-demo) already contains them in the `helm` directory.
You can also use [<ins>**our cookiecutter**</ins>](https://github.com/Blueshoe/hurricane-based-helm-template) for Helm charts for a Hurricane-based Django app.

To use it, run following command from your projects root directory:
~~~bash
cookiecutter gh:Blueshoe/hurricane-based-helm-template
~~~

You can use following answers for the prompt:
~~~bash
app_slug [project-name]: spacecrafts
description [Chart for the spacecrafts service]: Helm charts for the spacecrafts demo project
image_repo [quay.io/blueshoe/dj-hurricane-base]: quay.io/django-hurricane/spacecrafts-demo
Select use_imagePullSecret:
1 - yes
2 - no
Choose from 1, 2 [1]: 2
registry_username []: 
registry_password []: 
postgresql_version [10.13.7]: 
Select use_oauth2_proxy:
1 - yes
2 - no
Choose from 1, 2 [1]: 2
Select use_celery_worker:
1 - yes
2 - no
Choose from 1, 2 [1]: 2
Select use_celery_beat:
1 - yes
2 - no
Choose from 1, 2 [1]: 2
Select use_rabbitmq:
1 - yes
2 - no
Choose from 1, 2 [1]: 2
rabbitmq_version [8.18.1]: 
ampq_connect_image_repo [quay.io/blueshoe/amqp-connect]: 
~~~

You don't have to adapt any values or templates. The next step is to install the dependencies and the charts.
If you don't already have it locally available, you may need to add the [bitnami charts](https://github.com/bitnami/charts).
~~~bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm dep build spacecrafts
helm install spacecrafts spacecrafts/
~~~

We can check, which deployments and pods are running
~~~bash
kubectl get deployments
kubectl get pods
~~~
This way we can inspect the logs of a pod
~~~bash
kubectl logs -f spacecrafts-XXXXX-XXXXXXXX
~~~
By running this command we can get the url, which we can use to access the spacecrafts application
~~~bash
kubectl get ingress
~~~
You should be able to access the application using the ingress hostname, prepended by the port you specified when creating the k3d cluster (in this case [**spacecrafts.127.0.0.1.nip.io:8080**](http://spacecrafts.127.0.0.1.nip.io:8080))
and for instance you can access the graphql background at [**spacecrafts.127.0.0.1.nip.io:8080/graphql**](http://spacecrafts.127.0.0.1.nip.io:8080/graphql).

### Built-in Kubernetes probes and custom check handler

A big advantage of Django Hurricane is, that you don't need to write a lot of boilerplate code, i.e. probe handlers for Kubernetes probes,
hurricane takes care of it.

You can also create your own check handler.

For this, you can create a file named `src/apps/components/checks.py` with the following content:

~~~python
# src/apps/components/checks.py
import logging

from django.core.checks import Error

from apps.components.models import Component

logger = logging.getLogger("hurricane")


def example_check_main_engine(app_configs=None, **kwargs):
    """
    Check for existence of the "Main engine" component in the database
    """

    # your check logic here
    errors = []
    logger.info("Our check has been called :]")
    # we need to wrap all sync calls to the database into a sync_to_async wrapper for hurricane to use it in async way
    if not Component.objects.filter(title="Main engine").exists():
        errors.append(
            Error(
                "an error",
                hint="There is no main engine in the spacecraft, it need's to exist with the name 'Main engine'. "
                "Please create it in the admin or by installing the fixture.",
                id="components.E001",
            )
        )

    return errors
~~~

Important: if you have a synchronous call in your check to the database or other part of your app, make sure, that you
use `sync_to_async` to wrap those parts. Otherwise you will have problems with hurricane, as it expects all parts to be
asynchronous.

Next, we set a default app config in `apps/components/__init__.py`

~~~python
# src/apps/components/__init__.py
default_app_config = 'apps.components.apps.ComponentsConfig'
~~~

Now we need to register this check, so that Django can use it in its check logic. 
Note that we register the check with the tag `hurricane`, as Hurricane only runs check with that tag.
Your `apps/components/apps.py` should have following content:

~~~python
# apps/components/apps.py
from django.apps import AppConfig


class ComponentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.components"

    def ready(self):
        from django.core.checks import register

        from apps.components.checks import example_check_main_engine

        register(example_check_main_engine, "hurricane")
~~~

We register our check only after the application is ready, otherwise we will run into the error of AppNotReady.
This way we make sure, that this check is only registered after the application is ready, as check requires connection
to the model. 

To verify whether the check works, you can just delete the `Main engine` component from the database (if you don't use our image registry and you've just added the check, keep in mind that you need to build, push and deploy the image).
If you're running Hurricane locally, you can also directly browse to `/alive` at the probe port (`8001` if you've followed the first steps of the tutorial) to inspect its output.


### Local Kubernetes development: code hot-reloading, debugging and more

In order to comfortably further develop the spacecrafts app in the local cluster, we should absolutely have hot-reloading of the source code.

This can be done e.g. with local path mapping of k3d.

A more comfortable way to achieve this, with supported capabilities for debugging, is [<ins>**Gefyra**</ins>](https://gefyra.dev/).

If you want maximum convenience for your developers and a supported team oriented workflow, we recommend you check out [<ins>**Unikube**</ins>](https://unikube.io/).
