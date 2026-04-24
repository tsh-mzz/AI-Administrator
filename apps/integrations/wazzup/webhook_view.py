import asyncio
import hashlib
import hmac
import json
import structlog
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from apps.salons.models import Salon
from apps.integrations.wazzup.handler import WazzupHandler

logger = structlog.get_logger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class WazzupWebhookView(View):
    def post(self, request, salon_id: int):
        try:
            salon = Salon.objects.get(pk=salon_id, is_active=True)
        except Salon.DoesNotExist:
            return HttpResponse(status=404)

        # HMAC SHA256 validation
        signature = request.headers.get("X-Wazzup-Signature", "")
        body = request.body
        expected = hmac.new(
            salon.wazzup_api_key.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("wazzup_invalid_signature", salon_id=salon_id)
            return HttpResponse(status=401)

        update = json.loads(body)
        handler = WazzupHandler()
        asyncio.run(handler.handle_incoming_update(update=update, salon=salon))
        return JsonResponse({"ok": True})
