from .base import *  # noqa

DEBUG = True

INSTALLED_APPS += ["django_extensions"]  # noqa: F405

# Allow all hosts in dev
ALLOWED_HOSTS = ["*"]

# Show emails in console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Disable rate limiting in dev
RATELIMIT_ENABLE = False
