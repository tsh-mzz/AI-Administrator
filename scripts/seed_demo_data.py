"""
Run: python manage.py shell < scripts/seed_demo_data.py
Creates a demo salon with knowledge base documents for local testing.
"""
import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from apps.salons.models import Salon
from apps.knowledge_base.models import KnowledgeDocument, Service, Master

salon, _ = Salon.objects.get_or_create(
    name="Салон красоты Пример",
    defaults={
        "address": "ул. Примерная, 1",
        "phone": "+7 999 000-00-00",
        "timezone": "Europe/Moscow",
        "working_hours_json": {
            "mon": "10:00-21:00",
            "tue": "10:00-21:00",
            "wed": "10:00-21:00",
            "thu": "10:00-21:00",
            "fri": "10:00-21:00",
            "sat": "10:00-20:00",
            "sun": None,
        },
        "ai_model": "claude-sonnet-4-6",
    },
)
print(f"Salon: {salon.name} (id={salon.id})")

DOCS = [
    ("FAQ: Запись и отмена", "faq", """
Как записаться?
Напишите нам в чат или позвоните. Укажите желаемую услугу, мастера и удобное время.

Как отменить запись?
Сообщите нам не позднее чем за 2 часа до визита. Более поздняя отмена может облагаться штрафом 50% стоимости услуги.

Можно ли записаться онлайн?
Да, через этот чат. Бот поможет выбрать мастера, время и оформить запись.
"""),
    ("Прайс-лист: Волосы", "price", """
Стрижка женская — от 1500 руб, 60 мин
Стрижка мужская — от 900 руб, 45 мин
Окрашивание корней — от 2500 руб, 90 мин
Балаяж — от 5000 руб, 150 мин
Мелирование — от 3500 руб, 120 мин
Кератиновое выпрямление — от 6000 руб, 180 мин
Укладка — от 1200 руб, 45 мин
"""),
    ("Прайс-лист: Маникюр и педикюр", "price", """
Маникюр классический — от 1000 руб, 60 мин
Маникюр с покрытием гель-лак — от 1500 руб, 75 мин
Педикюр классический — от 1500 руб, 60 мин
Педикюр с покрытием — от 2000 руб, 90 мин
Снятие покрытия — 300 руб
Дизайн (за ноготь) — от 100 руб
"""),
    ("Политика салона", "policy", """
Просим приходить за 5 минут до начала процедуры.
Опоздание более 15 минут может сократить время процедуры или потребовать переноса.
Дети до 12 лет допускаются только в сопровождении взрослых.
Оплата наличными и картой.
"""),
    ("О мастерах", "general", """
Наши мастера имеют опыт от 3 до 15 лет. Все специалисты регулярно проходят обучение.
Старший мастер Анна специализируется на окрашивании и сложных техниках.
Мастер Елена — специалист по уходу за волосами и кератиновому выпрямлению.
Мастер Ирина — маникюр и педикюр, nail-art.
"""),
]

for title, doc_type, content in DOCS:
    doc, created = KnowledgeDocument.objects.get_or_create(
        salon=salon,
        title=title,
        defaults={"document_type": doc_type, "content": content.strip()},
    )
    print(f"  {'Created' if created else 'Exists'}: {title}")

print("\nDone! Now index documents:")
print("  from apps.knowledge_base.indexer import index_document_task")
print("  [index_document_task.delay(d.id) for d in KnowledgeDocument.objects.filter(salon_id=<id>)]")
