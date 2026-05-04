from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit


def healthz(request):
    return JsonResponse({"status": "ok"})


class _LoginViewBase(auth_views.LoginView):
    pass


RateLimitedLoginView = method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True),
    name="post",
)(_LoginViewBase)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("accounts/login/", RateLimitedLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("webhooks/telegram/", include("apps.integrations.telegram.urls")),
    path("webhooks/max/", include("apps.integrations.max.urls")),
    path("webhooks/wazzup/", include("apps.integrations.wazzup.urls")),
    path("salon/", include("apps.admin_panel.urls")),
]
