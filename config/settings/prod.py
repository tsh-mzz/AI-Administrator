from .base import *  # noqa
import environ

env = environ.Env()

DEBUG = False

# Railway auto-injects RAILWAY_PUBLIC_DOMAIN (e.g. "sm0rchki.up.railway.app").
# ALLOWED_HOSTS env var lets you add a custom domain later.
_railway_domain = env("RAILWAY_PUBLIC_DOMAIN", default="")
_extra_hosts = env.list("ALLOWED_HOSTS", default=[])
ALLOWED_HOSTS = list(filter(None, [_railway_domain] + _extra_hosts)) or ["localhost"]

# Railway terminates SSL and forwards X-Forwarded-Proto: https
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Trust the Railway domain (and any custom domain) for CSRF
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")
]
