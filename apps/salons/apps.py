import warnings

from django.apps import AppConfig


class SalonsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.salons"
    verbose_name = "Салоны"

    def ready(self):
        from django.conf import settings

        if not settings.DEBUG and not getattr(settings, "FIELD_ENCRYPTION_KEY", None):
            warnings.warn(
                "FIELD_ENCRYPTION_KEY is not set — sensitive salon fields will be stored in plaintext!",
                stacklevel=2,
            )
