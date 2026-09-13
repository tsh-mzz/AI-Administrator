# AI Administrator

A Claude AI-powered bot (Telegram and beyond) that answers client questions and creates bookings in YCLIENTS 24/7. One instance — multiple salons.

---

## Features

- Receives messages from **Telegram**, **MAX**, **WhatsApp**, and **Instagram Direct**
- Answers questions from knowledge base (RAG on Qdrant)
- Books appointments via **YCLIENTS API**
- Escalates non-standard situations to a human administrator
- Multi-tenant: one deployment serves multiple salons
- Web panel for the salon owner: knowledge base, conversations, statistics

---

## Stack

| Layer        | Technologies                                 |
| ------------ | -------------------------------------------- |
| Backend      | Python 3.12, Django 5, Django REST Framework |
| Database     | PostgreSQL 16                                |
| Cache/broker | Redis 7                                      |
| Queues       | Celery 5                                     |
| Vector DB    | Qdrant                                       |
| LLM          | Anthropic Claude (Sonnet)                    |
| Embeddings   | OpenAI `text-embedding-3-small`              |
| Messengers   | python-telegram-bot, Wazzup24 (WA + IG)      |
| CRM          | YCLIENTS API                                 |
| Deploy       | Docker Compose, Nginx, Let's Encrypt         |
| Monitoring   | Sentry, UptimeRobot                          |

---

## Quick Start (local development)

### Requirements

- Docker Desktop / docker-compose
- Python 3.12 (for linter and pre-commit outside the container)

### 1. Clone and configure environment variables

```bash
git clone <repo-url> salon_ai_bot
cd salon_ai_bot
cp .env.example .env
```

Open `.env` and fill in the required values:

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True

# PostgreSQL
POSTGRES_DB=salon_ai
POSTGRES_USER=salon_ai
POSTGRES_PASSWORD=changeme

# Redis
REDIS_URL=redis://redis:6379/0

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (for embeddings)
OPENAI_API_KEY=sk-...

# Telegram (for the test bot)
TELEGRAM_BOT_TOKEN=...

# Qdrant
QDRANT_URL=http://qdrant:6333
```

### 2. Start containers

```bash
docker compose up --build
```

Once running:

- Django: http://localhost:8000
- Django Admin: http://localhost:8000/admin
- Qdrant dashboard: http://localhost:6333/dashboard

### 3. Create a test

```bash
docker compose exec web python manage.py createsuperuser
```

Log in to `/admin` and create a `Salon` object with a Telegram bot token.

### 4. Register Telegram webhook (locally via ngrok)

```bash
ngrok http 8000
# Copy the https URL and register the webhook:
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<ngrok-id>.ngrok.io/webhooks/telegram/<salon-id>/"
```

---

## Project Structure

```
salon_ai_bot/
├── config/                  # Django settings (base / dev / prod)
├── apps/
│   ├── salons/              # Salon model, channel settings
│   ├── clients/             # Salon clients
│   ├── dialogs/             # AI engine, Celery tasks, history
│   ├── knowledge_base/      # RAG: indexing and search in Qdrant
│   ├── integrations/        # Telegram, MAX, Wazzup, YCLIENTS
│   └── admin_panel/         # Web panel for the salon owner
├── scripts/                 # Utilities: seed data, re-indexing
└── tests/
```

---

## Architecture

```
Client (Telegram / WA / IG)
         │
         ▼ webhook
Django REST API
         │
         ▼ task.delay()
Celery Worker
         │
    ┌────┴────────────────┐
    ▼                     ▼
AI Engine             YCLIENTS API
(Claude + RAG)        (create booking)
    │
    ├── Qdrant (vector search)
    ├── PostgreSQL (conversation history)
    └── Redis (cache, state)
```

Key principles:

- **Non-blocking webhooks** — all processing runs through Celery
- **Fail-safe** — any error → escalation to admin, clients never see stack traces
- **Client isolation** — all queries filtered by `salon_id`

---

## Configuration

Per-salon config is stored encrypted in the DB (via `django-cryptography`):

- Channel tokens (Telegram, Wazzup, MAX)
- YCLIENTS tokens
- Working hours
- System prompt override (optional)
- Admin Telegram ID for escalations

---

## Production Deploy

```bash
# On the server (Ubuntu 22.04, Docker installed)
git clone <repo-url> /opt/salon_ai_bot
cd /opt/salon_ai_bot
cp .env.example .env.prod
# Fill in .env.prod (DEBUG=False, real tokens)
docker compose -f docker-compose.prod.yml up -d
```

VPS requirements: 2 CPU / 4 GB RAM / 40 GB SSD.

After deploy:

1. Obtain SSL via certbot: `certbot --nginx -d yourdomain.com`
2. Register webhooks for all channels
3. Add `/healthz` to UptimeRobot

Full checklist in [PROJECT_PLAN.md](PROJECT_PLAN.md#12-деплой).

---

## Development

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run tests
docker compose exec web python manage.py test

# Re-index knowledge base
docker compose exec web python scripts/reindex_knowledge.py
```

---

## Security

- All tokens encrypted in DB (`django-cryptography`)
- Webhooks validated by signature (Telegram secret token, Wazzup HMAC SHA256)
- Rate limiting on webhooks and login form (`django-ratelimit`)
- System prompt protected against prompt injection (test cases in `tests/test_prompt_injection.py`)
- PII (phone numbers, names) masked in logs

---

## Cost per Conversation

- Claude Sonnet: ~$0.003 / 1K input tokens, ~$0.015 / 1K output tokens
- Average conversation (10 messages): **~$0.10–0.30**
- Too expensive? → Haiku fallback for simple questions (configurable via `ai_model` on the `Salon` model)

---

## License

Proprietary. All rights reserved.
