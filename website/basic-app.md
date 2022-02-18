---
layout: page
title: Guide to your first Hurricane-based Application
---
Content:
- [x] Create a basic django application
- [x] Run this application using django-hurricane
- [x] Create Kubernetes cluster

## 1. Create basic django application
We will make it a little bit more interesting and instead of a plain django application we will create a django-graphene application.
More about graphene you can learn [<ins>**here**</ins>](https://docs.graphene-python.org/projects/django/en/latest/). In it's essence, with 
django-graphene we will be able to use GraphQL functionality for our application.

> Alternatively, you can skip this part and clone [<ins>**this repository**</ins>](https://github.com/vvvityaaa/spacecrafts). You will also need to install 
> dependencies with <code>python -m pip install .</code>

> After that you can directly go to 
> [<ins>**run this application using Django Hurricane**</ins>](#2-run-this-application-using-django-hurricane)

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

Install Django and Django-Graphene
~~~bash
pip install django graphene_django
~~~

Set up a new project with a single application
~~~bash
django-admin startproject spacecrafts .  # Note:'.' character
cd spacecrafts
django-admin startapp components
~~~

Migrate initial changes
~~~bash
python manage.py migrate
~~~

Create model structures
~~~python
# spacecrafts/components/models.py
from django.db import models

class Category(models.Model):
    COMPONENT_CATEGORIES = [
        ('Power Source', 'Power Source'),
        ('Electronics', 'Electronics'),
        ('Hardware', 'Hardware'),
        ('Engines', 'Engines'),
        ('Safety Tools', 'Safety Tools'),
    ]
    title = models.CharField(
        max_length=100, choices=COMPONENT_CATEGORIES,
    )

    def __str__(self):
        return self.title


class Component(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    category = models.ForeignKey(
        Category, related_name="category", on_delete=models.CASCADE,
    )

    def __str__(self):
        return self.title
~~~
> Please refert to [<ins>**Django Documentation**</ins>](https://docs.djangoproject.com/en/4.0/topics/db/models/) for further information about Django models.

Add your new app `spacecrafts.components` as well as `graphene_django` to your settings file
~~~python
INSTALLED_APPS = [
    ...,
    'spacecrafts.components',
    'graphene_django',
]
~~~

Migrate changes
~~~bash
python manage.py makemigrations
python manage.py migrate
~~~

You can load fixture file from [<ins>**here**</ins>](Link to JSON file). It allows you to load data to your database from the fixture file, that defines several model instances
~~~bash
python manage.py loaddata ingredients
~~~
Alternatively you can create model instances on your own through the admin interface. For that you need to add following lines to your admin file:

~~~python
# spacecrafts/components/admin.py
from django.contrib import admin
from spacecrafts.components.models import Category, Component

admin.site.register(Category)
admin.site.register(Component)
~~~

Essential part of graphene_django is a graph representation of objects. To create such representation you need to create a so-called schema. Create schema.py file in your projects root with the following structure:

~~~python
# spacecrafts/schema.py
import graphene
from graphene_django import DjangoObjectType

from spacecrafts.components.models import Category, Component


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
        # We can easily optimize query count in the resolve method
        return Component.objects.select_related("category").all()

    def resolve_category_by_name(root, info, name):
        try:
            return Category.objects.get(name=name)
        except Category.DoesNotExist:
            return None


schema = graphene.Schema(query=Query)
~~~
> For more information on the concept of Schema, please refer to [<ins>**Graphene Documentation**</ins>](https://docs.graphene-python.org/projects/django/en/latest/schema/).

Now you just need to let django know, where it can find graphene schema. Add following setting to your settings file:
~~~python
# spacecrafts/settings.py

GRAPHENE = {
    "SCHEMA": "spacecrafts.schema.schema"
}
~~~

You also need to add a graphql endpoint to your urls file
~~~python
# spacecrafts/urls.py

from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from graphene_django.views import GraphQLView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("graphql", csrf_exempt(GraphQLView.as_view(graphiql=True))),
]
~~~

Now you can start the server
~~~bash
python manage.py runserver
~~~
After going to graphql url you can play around with GraphQL querying

## 2. Run this application using django-hurricane

Install django-hurricane in your virtual environment using command:

~~~bash
pip3 install django-hurricane
~~~

Add hurricane to your installed apps in django settings file:

~~~python
# spacecrafts/settings.py

INSTALLED_APPS = [
    ...
    'hurricane',
]
~~~

To have logs available, add the following logging setting to your settings file:

~~~python
# spacecrafts/settings.py

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
        "pika": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
~~~

Now you can start the server. With `--autoreload` flag server will be automatically reloaded upon the change in the code. Static files will be served if you add `--static` flag.
~~~bash
python manage.py serve --autoreload --static
~~~

You should get similar output upon the start of the server:
~~~bash
2022-01-21 10:19:21,434 INFO     hurricane.server.general Tornado-powered Django web server
2022-01-21 10:19:21,435 INFO     hurricane.server.general Autoreload was performed
2022-01-21 10:19:21,435 INFO     hurricane.server.general Starting probe application running on port 8001 with route liveness-probe: /alive, readiness-probe: /ready, startup-probe: /startup
2022-01-21 10:19:21,436 INFO     hurricane.server.general Starting HTTP Server on port 8000
2022-01-21 10:19:21,436 INFO     hurricane.server.general Serving static files under /static/ from None
2022-01-21 10:19:21,437 INFO     hurricane.server.general Startup time is 0.0026073455810546875 seconds
~~~

In addition to the previously defined `admin` and `graphql` endpoints, hurricane starts a probe server on port+1, unless another port is specified. This feature is essential for cloud-native development, and it is only one of the many features of django-hurricane. For further features and information on hurricane, please refer to [Full Django Hurricane Documentation](https://django-hurricane.readthedocs.io/en/latest/).


## 3. Create Kubernetes cluster

If you don't have a k3d yet, install it via
~~~bash
wget -q -O - https://raw.githubusercontent.com/rancher/k3d/main/install.sh | bash
~~~

After installing k3d you can create spacecrafts cluster via the following command

~~~bash
k3d cluster create spacecrafts --agents 1 -p 8080:80@agent:0 -p 31820:31820/UDP@agent:0
~~~

Next thing, we need to build a docker image and push it to the registry. If you want to use our public registry, please just skip this instructions, as we already have a registered image
~~~bash
docker build -t quay.io/{username}/spacecrafts:latest .
docker push quay.io/{username}/spacecrafts:latest
~~~
Now we need to install helm charts, which will define our cluster infrastructure. We have already prepared helm charts for you.
Just clone this repository [<ins>**spacecrafts-charts**</ins>](https://github.com/vvvityaaa/spacecrafts-charts). After that you can install these charts
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
kubectl logs -f buzzword-counter-web-XXXXX-XXXXXXXX
~~~
By running this command we can get the host name, which we can use to access the cluster
~~~bash
kubectl ingress
~~~
Now you should be able to access the application using the ingress hostname (in this case spacecrafts.127.0.0.1.nip.io)
and for instance you can access the graphql background at **spacecrafts.127.0.0.1.nip.io/graphql**.

A big advantage of Django Hurricane is, that you don't need to write a lot of boilerplate code, i.e. probe handlers for Kubernetes probes,
hurricane takes care of it.

You can check the inbuilt probes, going to **spacecrafts.127.0.0.1.nip.io/startup**, 
**spacecrafts.127.0.0.1.nip.io/alive** or **spacecrafts.127.0.0.1.nip.io/ready**. To learn more about probes, please refer to
[<ins>**hurricane probes**</ins>](https://django-hurricane.readthedocs.io/en/latest/api/server.html#module-hurricane.server.django).

Alternatively, you can create your own check handeler.

For this, you can create a file with a name checks.py with the following content:

~~~python
from django.core.checks import Error
from spacecrafts.components.models import Component
from asgiref.sync import sync_to_async
import logging

def example_check_main_engine(app_configs=None, **kwargs):
    '''
    Check for existance of the main engine in the database
    '''

    # your check logic here
    errors = []
    logging.info("Our check actully works!")
    # we need to wrap all sync calls to the database into a sync_to_async wrapper for hurricane to use it in async way
    if not sync_to_async(Component.objects.filter(title="Main engine").exists):
        errors.append(
            Error(
                'an error',
                hint='There is no main engine in the spacecraft.',
                id='components.E001',
            )
        )

    return errors
~~~

Important: if you have synchronous call in your check to the database or other part of your app, make sure, that you
use sync_to_async to wrap those parts or otherwise you will have problems with hurricane, as it expects all parts to be
asynchronous.

Now we need to register this check, so that Django can use it in it's check logic.
from django.apps import AppConfig

~~~python
from django.apps import AppConfig


class ComponentsConfig(AppConfig):
    name = 'spacecrafts.components'

    def ready(self):
        from spacecrafts.components.checks import example_check_main_engine
        from django.core.checks import register
        register(example_check_main_engine)
~~~

Here we register our check only after the application is ready, otherwise we will run into the error of AppNotReady.
This way we make sure, that this check is only registered after the application is ready, as check requires connection
to the model.

If you will now go to **spacecrafts.127.0.0.1.nip.io/alive**, you will see the message "Our check actully works!" in
the logs. It means, that our check will be invoked every time alive-probe will be requested. This way you can write
custom checks with your own logic in them.
