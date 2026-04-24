from django.urls import path
from .webhook_view import WazzupWebhookView

urlpatterns = [
    path("<int:salon_id>/", WazzupWebhookView.as_view(), name="wazzup-webhook"),
]
