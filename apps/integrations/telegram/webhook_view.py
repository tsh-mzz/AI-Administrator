import json
import asyncio
import structlog
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from apps.salons.models import Salon
from apps.integrations.telegram.handler import TelegramHandler

logger = structlog.get_logger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class TelegramWebhookView(View):
    """
    URL: /webhooks/telegram/<salon_id>/
    Telegram sends updates here. Validated by secret_token header.
    """

    def post(self, request, salon_id: int):
        # Validate secret token set when registering webhook
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        try:
            salon = Salon.objects.get(pk=salon_id, is_active=True)
        except Salon.DoesNotExist:
            return HttpResponse(status=404)

        expected_secret = _get_webhook_secret(salon)
        if not secret or secret != expected_secret:
            logger.warning("telegram_webhook_invalid_secret", salon_id=salon_id)
            return HttpResponse(status=401)

        try:
            update = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse(status=400)

        handler = TelegramHandler()
        asyncio.run(handler.handle_incoming_update(update=update, salon=salon))

        return JsonResponse({"ok": True})


def _get_webhook_secret(salon) -> str:
    """Derive per-salon webhook secret from bot token hash."""
    import hashlib
    token = salon.telegram_bot_token or ""
    return hashlib.sha256(token.encode()).hexdigest()[:32]
