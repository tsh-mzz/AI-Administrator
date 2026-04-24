from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def healthz(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("webhooks/telegram/", include("apps.integrations.telegram.urls")),
    path("webhooks/wazzup/", include("apps.integrations.wazzup.urls")),
    path("salon/", include("apps.admin_panel.urls")),
]
