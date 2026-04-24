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

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="knowledge_docs")
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
    """Synced from YCLIENTS, read-only except description."""

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="services")
    yclients_id = models.IntegerField()
    title = models.CharField(max_length=300)
    category = models.CharField(max_length=200, blank=True)
    duration_minutes = models.IntegerField()
    price_min = models.DecimalField(max_digits=10, decimal_places=2)
    price_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
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
    yclients_id = models.IntegerField()
    name = models.CharField(max_length=200)
    specialization = models.CharField(max_length=300, blank=True)
    bio = models.TextField(blank=True)
    service_ids = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("salon", "yclients_id")]
        verbose_name = "Мастер"
        verbose_name_plural = "Мастера"

    def __str__(self):
        return f"{self.name} ({self.salon.name})"
