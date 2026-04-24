from django.urls import path
from . import views

urlpatterns = [
    path("<int:salon_id>/dashboard/", views.dashboard, name="salon-dashboard"),
    path("<int:salon_id>/dialogs/", views.dialogs_list, name="salon-dialogs"),
    path("<int:salon_id>/dialogs/<int:conversation_id>/", views.dialog_detail, name="salon-dialog-detail"),
    path("<int:salon_id>/knowledge/", views.knowledge_list, name="salon-knowledge"),
    path("<int:salon_id>/escalations/", views.escalations, name="salon-escalations"),
    path("<int:salon_id>/settings/", views.salon_settings, name="salon-settings"),
]
