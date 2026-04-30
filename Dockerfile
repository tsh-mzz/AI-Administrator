FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Bake static files into the image so they're available at runtime.
# collectstatic doesn't touch the DB, so a dummy SECRET_KEY is fine here.
RUN DJANGO_SETTINGS_MODULE=config.settings.prod \
    SECRET_KEY=collectstatic-build-only \
    FIELD_ENCRYPTION_KEY=YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE= \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Default command for local Docker runs.
# Railway overrides this via railway.toml startCommand.
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
