from django.urls import path
from .webhook_view import TelegramWebhookView

urlpatterns = [
    path("<int:salon_id>/", TelegramWebhookView.as_view(), name="telegram-webhook"),
]
