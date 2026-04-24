from django.db import models
from apps.salons.models import Salon


class SalonClient(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="clients")
    external_id_yclients = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    phone = models.CharField(max_length=20, db_index=True)
    name = models.CharField(max_length=200, blank=True)
    preferred_channel = models.CharField(max_length=20, blank=True)
    last_visit_date = models.DateTimeField(null=True, blank=True)
    total_visits = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("salon", "phone")]
        indexes = [models.Index(fields=["salon", "external_id_yclients"])]
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"

    def __str__(self):
        return f"{self.name or self.phone} ({self.salon.name})"
