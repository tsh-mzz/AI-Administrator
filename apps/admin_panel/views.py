from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from datetime import timedelta

from apps.salons.models import Salon
from apps.dialogs.models import Conversation, Message
from apps.knowledge_base.models import KnowledgeDocument


def _get_salon_or_403(request, salon_id: int) -> Salon:
    return get_object_or_404(Salon, pk=salon_id, is_active=True)


@login_required
def dashboard(request, salon_id: int):
    salon = _get_salon_or_403(request, salon_id)
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    stats = {
        "messages_today": Message.objects.filter(
            conversation__salon=salon, created_at__gte=today_start
        ).count(),
        "bookings_total": Conversation.objects.filter(
            salon=salon, messages__tool_calls_json__icontains="create_booking"
        ).distinct().count(),
        "escalations_open": Conversation.objects.filter(
            salon=salon, status="handed_to_admin"
        ).count(),
        "active_conversations": Conversation.objects.filter(
            salon=salon, status="active"
        ).count(),
    }
    return render(request, "admin_panel/dashboard.html", {"salon": salon, "stats": stats})


@login_required
def dialogs_list(request, salon_id: int):
    salon = _get_salon_or_403(request, salon_id)
    channel = request.GET.get("channel")
    status = request.GET.get("status")

    qs = Conversation.objects.filter(salon=salon).order_by("-last_message_at")
    if channel:
        qs = qs.filter(channel=channel)
    if status:
        qs = qs.filter(status=status)

    return render(request, "admin_panel/dialogs.html", {"salon": salon, "conversations": qs})


@login_required
def dialog_detail(request, salon_id: int, conversation_id: int):
    salon = _get_salon_or_403(request, salon_id)
    conversation = get_object_or_404(Conversation, pk=conversation_id, salon=salon)
    messages = conversation.messages.order_by("created_at")
    return render(request, "admin_panel/dialog_detail.html", {
        "salon": salon,
        "conversation": conversation,
        "messages": messages,
    })


@login_required
def knowledge_list(request, salon_id: int):
    salon = _get_salon_or_403(request, salon_id)
    docs = KnowledgeDocument.objects.filter(salon=salon).order_by("-updated_at")
    return render(request, "admin_panel/knowledge.html", {"salon": salon, "docs": docs})


@login_required
def escalations(request, salon_id: int):
    salon = _get_salon_or_403(request, salon_id)
    convs = Conversation.objects.filter(salon=salon, status="handed_to_admin").order_by("-last_message_at")
    return render(request, "admin_panel/escalations.html", {"salon": salon, "conversations": convs})


@login_required
def salon_settings(request, salon_id: int):
    salon = _get_salon_or_403(request, salon_id)
    return render(request, "admin_panel/settings.html", {"salon": salon})
