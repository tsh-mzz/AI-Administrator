from django.db import models
from apps.salons.models import Salon


class KnowledgeDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ("faq", "FAQ"),
        ("policy", "Policy"),
        ("price", "Price info"),
        ("service_description", "Service description"),
        ("general", "General"),
    ]

    salon = models.ForeignKey(
        Salon, on_delete=models.CASCADE, related_name="knowledge_docs"
    )
    title = models.CharField(max_length=300)
    content = models.TextField()
    document_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    qdrant_point_ids = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Документ базы знаний"
        verbose_name_plural = "База знаний"

    def __str__(self):
        return f"{self.title} ({self.salon.name})"


class Service(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="services")
    # Null for salons without YCLIENTS; filled for YCLIENTS-synced salons
    yclients_id = models.IntegerField(null=True, blank=True)
    title = models.CharField(max_length=300)
    category = models.CharField(max_length=200, blank=True)
    duration_minutes = models.IntegerField()
    price_min = models.DecimalField(max_digits=10, decimal_places=2)
    price_max = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("salon", "yclients_id")]
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"

    def __str__(self):
        return f"{self.title} ({self.salon.name})"


class Master(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="masters")
    # Null for salons without YCLIENTS
    yclients_id = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=200)
    specialization = models.CharField(max_length=300, blank=True)
    bio = models.TextField(blank=True)
    experience_years = models.IntegerField(null=True, blank=True)
    services = models.ManyToManyField(Service, blank=True, related_name="masters")
    is_active = models.BooleanField(default=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("salon", "yclients_id")]
        verbose_name = "Мастер"
        verbose_name_plural = "Мастера"

    def __str__(self):
        return f"{self.name} ({self.salon.name})"


class Booking(models.Model):
    STATUS_CHOICES = [
        ("confirmed", "Подтверждено"),
        ("cancelled", "Отменено"),
        ("completed", "Завершено"),
        ("no_show", "Не пришёл"),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="bookings")
    client_name = models.CharField(max_length=200)
    client_phone = models.CharField(max_length=20)
    service = models.ForeignKey(
        Service, on_delete=models.PROTECT, related_name="bookings"
    )
    master = models.ForeignKey(
        Master,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bookings",
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="confirmed"
    )
    notes = models.TextField(blank=True)
    reminder_sent = models.BooleanField(default=False)
    conversation = models.ForeignKey(
        "dialogs.Conversation", null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["salon", "starts_at"]),
            models.Index(fields=["master", "starts_at"]),
        ]
        verbose_name = "Запись"
        verbose_name_plural = "Записи"

    def __str__(self):
        return f"{self.client_name} → {self.service.title} {self.starts_at:%d.%m %H:%M}"
