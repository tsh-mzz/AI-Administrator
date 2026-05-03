from django.conf import settings
from django.db import models
from apps.salons.fields import EncryptedCharField


class Salon(models.Model):
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="salons",
    )
    address = models.CharField(max_length=500)
    phone = models.CharField(max_length=20)
    timezone = models.CharField(max_length=50, default="Europe/Moscow")

    # YCLIENTS
    yclients_company_id = models.IntegerField(null=True, blank=True)
    yclients_user_token = EncryptedCharField(null=True, blank=True)
    yclients_partner_token = EncryptedCharField(null=True, blank=True)

    # Channels
    telegram_bot_token = EncryptedCharField(null=True, blank=True)
    telegram_bot_username = models.CharField(max_length=100, null=True, blank=True)
    max_bot_token = EncryptedCharField(null=True, blank=True)
    wazzup_api_key = EncryptedCharField(null=True, blank=True)
    wazzup_channel_id_whatsapp = models.CharField(max_length=100, null=True, blank=True)
    wazzup_channel_id_instagram = models.CharField(
        max_length=100, null=True, blank=True
    )

    # AI settings
    system_prompt_override = models.TextField(blank=True)
    ai_model = models.CharField(max_length=50, default="gpt-4o-mini")

    # Operational
    admin_telegram_id = models.CharField(max_length=50, null=True, blank=True)
    working_hours_json = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Салон"
        verbose_name_plural = "Салоны"

    def __str__(self):
        return self.name
