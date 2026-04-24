# Sm0rchki — ИИ-администратор

Telegram-бот (и не только) на базе Claude AI, который отвечает на вопросы клиентов и создаёт записи в YCLIENTS в режиме 24/7. Один инстанс — несколько салонов.

---

## Что умеет

- Принимает сообщения из **Telegram**, **MAX**, **WhatsApp** и **Instagram Direct**
- Отвечает на вопросы по базе знаний (RAG на Qdrant)
- Записывает клиентов через **YCLIENTS API**
- Эскалирует нестандартные ситуации администратору
- Multi-tenant: один деплой обслуживает несколько салонов
- Веб-панель для владельца: база знаний, диалоги, статистика

---

## Стек

| Слой         | Технологии                                   |
| ------------ | -------------------------------------------- |
| Бэкенд       | Python 3.12, Django 5, Django REST Framework |
| База данных  | PostgreSQL 16                                |
| Кэш / брокер | Redis 7                                      |
| Очереди      | Celery 5                                     |
| Векторная БД | Qdrant                                       |
| LLM          | Anthropic Claude (Sonnet)                    |
| Embeddings   | OpenAI `text-embedding-3-small`              |
| Мессенджеры  | python-telegram-bot, Wazzup24 (WA + IG)      |
| CRM          | YCLIENTS API                                 |
| Деплой       | Docker Compose, Nginx, Let's Encrypt         |
| Мониторинг   | Sentry, UptimeRobot                          |

---

## Быстрый старт (локальная разработка)

### Требования

- Docker Desktop / docker-compose
- Python 3.12 (для линтера и pre-commit вне контейнера)

### 1. Клонировать и настроить переменные окружения

```bash
git clone <repo-url> salon_ai_bot
cd salon_ai_bot
cp .env.example .env
```

Открыть `.env` и заполнить обязательные значения:

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

# OpenAI (для embeddings)
OPENAI_API_KEY=sk-...

# Telegram (для тестового бота)
TELEGRAM_BOT_TOKEN=...

# Qdrant
QDRANT_URL=http://qdrant:6333
```

### 2. Поднять контейнеры

```bash
docker compose up --build
```

После старта доступно:

- Django: http://localhost:8000
- Django Admin: http://localhost:8000/admin
- Qdrant dashboard: http://localhost:6333/dashboard

### 3. Создать тестовый салон

```bash
docker compose exec web python manage.py createsuperuser
```

Войти в `/admin`, создать объект `Salon` с токеном Telegram-бота.

### 4. Подключить вебхук Telegram (локально через ngrok)

```bash
ngrok http 8000
# Скопировать https-URL и зарегистрировать вебхук:
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<ngrok-id>.ngrok.io/webhooks/telegram/<salon-id>/"
```

---

## Структура проекта

```
salon_ai_bot/
├── config/                  # Django settings (base / dev / prod)
├── apps/
│   ├── salons/              # Модель Salon, настройки каналов
│   ├── clients/             # Клиенты салонов
│   ├── dialogs/             # AI-движок, Celery tasks, история
│   ├── knowledge_base/      # RAG: индексация и поиск в Qdrant
│   ├── integrations/        # Telegram, MAX, Wazzup, YCLIENTS
│   └── admin_panel/         # Веб-панель для владельца салона
├── scripts/                 # Утилиты: seed-данные, переиндексация
└── tests/
```

---

## Архитектура

```
Клиент (Telegram / WA / IG)
         │
         ▼ вебхук
Django REST API
         │
         ▼ task.delay()
Celery Worker
         │
    ┌────┴────────────────┐
    ▼                     ▼
AI Engine             YCLIENTS API
(Claude + RAG)        (создать запись)
    │
    ├── Qdrant (векторный поиск)
    ├── PostgreSQL (история диалогов)
    └── Redis (кэш, состояния)
```

Ключевые принципы:

- **Вебхук не блокируется** — вся обработка через Celery
- **Fail-safe** — любая ошибка → эскалация администратору, клиент не видит стектрейсы
- **Изоляция клиентов** — везде фильтрация по `salon_id`

---

## Конфигурация

Хранит в БД (зашифровано через `django-cryptography`):

- Токены каналов (Telegram, Wazzup, MAX)
- Токены YCLIENTS
- Часы работы
- System prompt override (опционально)
- Telegram ID администратора для эскалаций

---

## Деплой на продакшен

```bash
# На сервере (Ubuntu 22.04, Docker установлен)
git clone <repo-url> /opt/salon_ai_bot
cd /opt/salon_ai_bot
cp .env.example .env.prod
# Заполнить .env.prod (DEBUG=False, реальные токены)
docker compose -f docker-compose.prod.yml up -d
```

Требования к VPS: 2 CPU / 4 GB RAM / 40 GB SSD (~1500–2500 руб/мес на Selectel / Timeweb).

После деплоя:

1. Получить SSL через certbot: `certbot --nginx -d yourdomain.ru`
2. Настроить вебхуки для всех каналов
3. Добавить `/healthz` в UptimeRobot

Подробный чеклист — в [PROJECT_PLAN.md](PROJECT_PLAN.md#12-деплой).

---

## Разработка

```bash
# Установить pre-commit хуки
pip install pre-commit
pre-commit install

# Запустить тесты
docker compose exec web python manage.py test

# Переиндексировать базу знаний
docker compose exec web python scripts/reindex_knowledge.py
```

---

## Безопасность

- Все токены шифруются в БД (`django-cryptography`)
- Вебхуки валидируются по подписи (Telegram secret token, Wazzup HMAC SHA256)
- Rate limiting на вебхуках и форме входа (`django-ratelimit`)
- System prompt защищён от prompt injection (тест-кейсы в `tests/test_prompt_injection.py`)
- PII (телефоны, имена) маскируются в логах

---

## Стоимость диалога

- Claude Sonnet: ~$0.003 / 1K input tokens, ~$0.015 / 1K output tokens
- Средний диалог (10 сообщений): **10–30 руб**
- Если дорого → Haiku fallback для простых вопросов (настраивается через `ai_model` в Salon)

---

## Лицензия

Проприетарный код. Все права защищены.
