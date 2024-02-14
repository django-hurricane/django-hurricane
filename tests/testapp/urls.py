import ctypes

from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.urls import path


def test_view(request):
    return HttpResponse("Hello world!", status=200)


def medium_view(request):
    from django.contrib.contenttypes.models import ContentType

    user_type = ContentType.objects.get(app_label="auth", model="user")
    # time.sleep(0.1)
    return HttpResponse(str(user_type), status=200)


def heavy_view(request):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    users = User.objects.all()
    # time.sleep(0.5)
    return HttpResponse(str(users), status=200)


def memory_leak_view(request):
    def memleak():
        # Create C api callable
        inc_ref = ctypes.pythonapi.Py_IncRef
        inc_ref.argtypes = [ctypes.py_object]
        inc_ref.restype = None

        # Allocate a large object
        obj = list(range(200000))

        # Increment its ref count
        inc_ref(obj)

        # obj will have a dangling reference after this function exits

    memleak()
    return HttpResponse("Memory was leaked", status=200)


urlpatterns = [
    path("", test_view),
    path("medium", medium_view),
    path("heavy", heavy_view),
    path("memory", memory_leak_view),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
