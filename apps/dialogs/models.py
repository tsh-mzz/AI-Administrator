from django.db import models
from apps.salons.models import Salon
from apps.clients.models import SalonClient


class Conversation(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("handed_to_admin", "Handed to admin"),
        ("closed", "Closed"),
    ]
    CHANNEL_CHOICES = [
        ("telegram", "Telegram"),
        ("max", "MAX"),
        ("whatsapp", "WhatsApp"),
        ("instagram", "Instagram"),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="conversations")
    client = models.ForeignKey(SalonClient, null=True, blank=True, on_delete=models.SET_NULL)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    external_chat_id = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    context_json = models.JSONField(default=dict)
    escalation_reason = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("salon", "channel", "external_chat_id")]
        indexes = [models.Index(fields=["salon", "status"])]
        verbose_name = "Диалог"
        verbose_name_plural = "Диалоги"

    def __str__(self):
        return f"{self.channel}:{self.external_chat_id} ({self.salon.name})"


class Message(models.Model):
    DIRECTION_CHOICES = [("in", "Incoming"), ("out", "Outgoing")]
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
        ("tool", "Tool"),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    tool_calls_json = models.JSONField(null=True, blank=True)
    tool_results_json = models.JSONField(null=True, blank=True)

    # Metrics
    tokens_input = models.IntegerField(null=True, blank=True)
    tokens_output = models.IntegerField(null=True, blank=True)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)

    external_message_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["conversation", "created_at"])]
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"
