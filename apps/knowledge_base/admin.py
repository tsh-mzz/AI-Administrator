from django.contrib import admin
from .models import Booking, KnowledgeDocument, Master, Service


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "salon", "document_type", "is_active", "updated_at")
    list_filter = ("salon", "document_type", "is_active")
    search_fields = ("title", "content")
    readonly_fields = ("qdrant_point_ids", "updated_at")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Trigger re-indexing when document is saved via admin
        from apps.knowledge_base.tasks import index_document_task

        index_document_task.delay(obj.id)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "salon",
        "category",
        "duration_minutes",
        "price_min",
        "price_max",
        "is_active",
    )
    list_filter = ("salon", "category", "is_active")
    search_fields = ("title",)
    readonly_fields = ("yclients_id", "synced_at")


@admin.register(Master)
class MasterAdmin(admin.ModelAdmin):
    list_display = ("name", "salon", "specialization", "experience_years", "is_active")
    list_filter = ("salon", "is_active")
    search_fields = ("name",)
    readonly_fields = ("synced_at",)
    filter_horizontal = ("services",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "client_name",
        "client_phone",
        "service",
        "master",
        "starts_at",
        "status",
    )
    list_filter = ("salon", "status", "master")
    search_fields = ("client_name", "client_phone")
    readonly_fields = ("created_at",)
    date_hierarchy = "starts_at"
