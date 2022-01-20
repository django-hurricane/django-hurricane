---
layout: page
title: Getting started with Hurricane
---
## 1. You need an IDE
You can choose whatever IDE you like. For remote Python debugging to work you need an
IDE which supports [**debugpy**](https://pypi.org/project/debugpy/) or [**pydevd**](https://pypi.org/project/pydevd/), like VS Code or PyCharm. 

## 2. Start a project with Django
Start a new Django-based project as you like.  

Be sure to check out the specifically created 
[**cookiecutter**](https://cookiecutter.readthedocs.io/en/latest/) template [**django-hurricane-template**](https://github.com/Blueshoe/django-hurricane-template). 
With that, you can run 
~~~bash
cookiecutter gh:Blueshoe/django-hurricane-template
~~~
and you'll get a Hurricane-based project layout created for you. In that case, you can head over straight to
point 5.

## 3. Install Hurricane to your environment
Hurricane can be installed from Python Package Index with
~~~bash
pip3 install django-hurricane
~~~

## 4. Add it to your *INSTALLED_APPS*

Add *"hurricane"* to your INSTALLED_APPS:
~~~python
INSTALLED_APPS += (
    'hurricane',
)
~~~

## 5. Start coding
You can run a development server exactly the same way you would run the production server. It is realized
with a Django management command:
~~~bash
python manage.py serve --autoreload --static
~~~
That will start a Tornado-based web server that hot-reloads your code upon changes. It will serve your static
and media files, too.
<div class="jumbotron dh-color">
    <p class="lead">For detailed configuration parameters please refer to the documentation of <a href="https://django-hurricane.readthedocs.io/en/latest/usage.html#application-server">Hurricane's application server</a>.</p>
</div>

## 6. Test your application in Kubernetes
In order to run your fancy new application in Kubernetes you will need workload manifests. You can write them yourself
or generate them from our specifically prepared [**cookiecutter**](https://cookiecutter.readthedocs.io/en/latest/) 
Helm charts template [**hurricane-based-helm-template**](https://github.com/Blueshoe/hurricane-based-helm-template).
Just run the following command, answer the questions accordingly and you will get ready-to-go Helm charts: 
~~~bash
cookiecutter gh:Blueshoe/hurricane-based-helm-template
~~~
Go on and select your favorite Kubernetes-distributon for development. Besides others, [**k3d**](https://k3d.io) works very well.
Be sure to have [Helm](https://helm.sh/) installed and go on with:
~~~bash
helm install my-release <app-name>/
~~~

That's it. You can now hand over everything to production, relax and let Kubernetes operate your Django application 
(almost) hassle-free.



