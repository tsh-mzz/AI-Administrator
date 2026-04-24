from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "direction", "content", "tokens_input", "tokens_output", "cost_usd", "latency_ms", "created_at")
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("salon", "channel", "external_chat_id", "status", "last_message_at")
    list_filter = ("salon", "channel", "status")
    search_fields = ("external_chat_id",)
    readonly_fields = ("started_at", "last_message_at")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "direction", "content_preview", "cost_usd", "created_at")
    list_filter = ("role", "direction")
    readonly_fields = ("created_at",)

    def content_preview(self, obj):
        return obj.content[:80]
    content_preview.short_description = "Content"
