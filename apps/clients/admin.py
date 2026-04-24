from django.contrib import admin
from .models import SalonClient


@admin.register(SalonClient)
class SalonClientAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "salon", "preferred_channel", "total_visits", "last_visit_date")
    list_filter = ("salon", "preferred_channel")
    search_fields = ("name", "phone")
    readonly_fields = ("created_at",)
