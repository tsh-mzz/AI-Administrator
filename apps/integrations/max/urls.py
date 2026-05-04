from django.urls import path
from .webhook_view import MaxWebhookView

urlpatterns = [
    path("<int:salon_id>/", MaxWebhookView.as_view(), name="max-webhook"),
]
