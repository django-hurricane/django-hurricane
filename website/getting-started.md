---
layout: page
title: GETTING STARTED WITH HURRICANE
---
## 1. You need an IDE
You can chose what ever IDE you like. For remote Python debugging to work you need an
IDE which supports [**debugpy**](https://pypi.org/project/debugpy/) or [**pydevd**](https://pypi.org/project/pydevd/), like VS Code or PyCharm. 

## 2. Start a project with django
Start a new django-based project as you like.  

Be sure to check out the specifically created 
[**cookiecutter**](https://cookiecutter.readthedocs.io/en/latest/) template [**django-hurricane-template**](https://github.com/Blueshoe/django-hurricane-template). 
With that you can run 
~~~bash
cookiecutter gh:Blueshoe/django-hurricane-template
~~~
and you'll get a Hurricane-based project layout created for you. In that case you can straight head over to
point 5.

## 3. Install Hurricane to you environment
Hurricane can be installed from Python Package Index with
~~~bash
pip3 install hurricane
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
python manage.py serve --autoreload --static --media
~~~
That will start a Tornado-based web server that hot-reloads your code upon changes. It will serve your static
and media files, too.
<div class="jumbotron dh-color">
    <p class="lead">For detailed configuration parameters please refer to the documentation of <a href="https://django-hurricane.readthedocs.io/en/latest/usage.html#application-server">Hurricane's application server</a>.</p>
</div>

