import json
import structlog
from asgiref.sync import async_to_sync
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from apps.salons.models import Salon
from apps.integrations.max.handler import MaxHandler

logger = structlog.get_logger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(
    ratelimit(key="ip", rate="100/m", method="POST", block=True), name="dispatch"
)
class MaxWebhookView(View):
    """
    URL: /webhooks/max/<salon_id>/
    MAX sends updates here. Token verified via salon lookup.
    """

    def get(self, request, salon_id: int):
        # MAX sends a GET with hub.challenge for webhook verification
        challenge = request.GET.get("hub.challenge")
        if challenge:
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse(status=200)

    def post(self, request, salon_id: int):
        try:
            salon = Salon.objects.get(pk=salon_id, is_active=True)
        except Salon.DoesNotExist:
            return HttpResponse(status=404)

        if not salon.max_bot_token:
            return HttpResponse(status=403)

        try:
            update = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse(status=400)

        handler = MaxHandler()
        async_to_sync(handler.handle_incoming_update)(update=update, salon=salon)

        return JsonResponse({"ok": True})
