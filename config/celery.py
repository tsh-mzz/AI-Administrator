import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("salon_ai")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.autodiscover_tasks(["apps.integrations.yclients"], related_name="sync")
