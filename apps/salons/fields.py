from django.conf import settings
from django.db import models


def _fernet():
    from cryptography.fernet import Fernet

    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedCharField(models.TextField):
    """
    Stores values encrypted with Fernet (symmetric AES-128-CBC + HMAC).
    Requires FIELD_ENCRYPTION_KEY (a valid Fernet key) in settings.
    Falls back to plaintext when key is not set (local dev without .env).
    """

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        f = _fernet()
        if f is None:
            return value
        try:
            return f.decrypt(value.encode()).decode()
        except Exception:
            return value

    def get_prep_value(self, value):
        if not value:
            return value
        f = _fernet()
        if f is None:
            return value
        return f.encrypt(value.encode()).decode()

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, "apps.salons.fields.EncryptedCharField", args, kwargs
