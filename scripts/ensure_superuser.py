"""Idempotently create a Django superuser from env vars.

Reads DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD. No-op if any are missing
or the user already exists. Run via `python manage.py shell < scripts/ensure_superuser.py`.
"""

import os

from django.contrib.auth import get_user_model

username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

if not username or not password:
    print("ensure_superuser: DJANGO_SUPERUSER_USERNAME/PASSWORD not set, skipping")
else:
    User = get_user_model()
    if User.objects.filter(username=username).exists():
        print(f"ensure_superuser: user {username!r} already exists, skipping")
    else:
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f"ensure_superuser: created superuser {username!r}")
