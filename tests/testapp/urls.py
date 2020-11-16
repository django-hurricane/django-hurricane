from django.http import HttpResponse
from django.urls import path


def test_view(request):
    return HttpResponse("Hello world!", status=200)


urlpatterns = [path("", test_view)]
