from django.contrib import admin
from .models import KnowledgeDocument, Service, Master


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
    list_display = ("title", "salon", "category", "duration_minutes", "price_min", "price_max", "is_active")
    list_filter = ("salon", "category", "is_active")
    search_fields = ("title",)
    readonly_fields = ("yclients_id", "synced_at")


@admin.register(Master)
class MasterAdmin(admin.ModelAdmin):
    list_display = ("name", "salon", "specialization", "is_active")
    list_filter = ("salon", "is_active")
    search_fields = ("name",)
    readonly_fields = ("yclients_id", "synced_at")
