from django.contrib import admin
from .models import Salon


@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "timezone", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "phone")
    readonly_fields = ("created_at",)
