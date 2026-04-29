"""
Populate Salon pk=1 with realistic demo data (no YCLIENTS required).

Usage:
    python manage.py seed_demo_salon
    python manage.py seed_demo_salon --salon-id 2   # different salon
    python manage.py seed_demo_salon --clear        # wipe before seeding
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


SERVICES = [
    # (title, category, duration_min, price_min, price_max, description)
    (
        "Маникюр классический",
        "Маникюр",
        60,
        1200,
        None,
        "Классический маникюр с обработкой кутикулы и покрытием лаком на выбор.",
    ),
    (
        "Маникюр с гель-лаком",
        "Маникюр",
        90,
        1800,
        None,
        "Маникюр с долгосрочным гель-лаковым покрытием, держится до 3 недель.",
    ),
    (
        "Педикюр классический",
        "Педикюр",
        75,
        1500,
        None,
        "Классический педикюр с обработкой стопы и покрытием лаком.",
    ),
    (
        "Педикюр с гель-лаком",
        "Педикюр",
        120,
        2000,
        None,
        "Педикюр с гель-лаковым покрытием, идеален для летнего сезона.",
    ),
    (
        "Стрижка женская",
        "Волосы",
        60,
        1500,
        2500,
        "Стрижка любой сложности с укладкой. Цена зависит от длины волос.",
    ),
    (
        "Стрижка мужская",
        "Волосы",
        30,
        800,
        None,
        "Мужская стрижка машинкой или ножницами с укладкой.",
    ),
    (
        "Окрашивание однотонное",
        "Волосы",
        120,
        3500,
        5000,
        "Однотонное окрашивание профессиональными красками Wella. Цена зависит от длины.",
    ),
    (
        "Мелирование / балаяж",
        "Волосы",
        180,
        5500,
        9000,
        "Сложное окрашивание: мелирование, балаяж, омбре. Уточняйте у мастера.",
    ),
    (
        "Укладка",
        "Волосы",
        45,
        1000,
        1500,
        "Профессиональная укладка феном или щипцами.",
    ),
    (
        "Коррекция бровей",
        "Брови и ресницы",
        30,
        800,
        None,
        "Коррекция формы бровей воском или нитью.",
    ),
    (
        "Окрашивание бровей",
        "Брови и ресницы",
        20,
        600,
        None,
        "Окрашивание бровей хной или краской, держится до 4 недель.",
    ),
    (
        "Ламинирование ресниц",
        "Брови и ресницы",
        90,
        2500,
        None,
        "Ламинирование придаёт ресницам объём и изгиб без завивки. Эффект до 6 недель.",
    ),
    (
        "Наращивание ресниц",
        "Брови и ресницы",
        150,
        3500,
        5000,
        "Классическое или объёмное наращивание. Коррекция через 2-3 недели.",
    ),
]

MASTERS = [
    # (name, specialization, experience_years, bio, service_titles)
    (
        "Оля Иванова",
        "Маникюр и педикюр",
        5,
        "Оля специализируется на маникюре и педикюре уже 5 лет. "
        "Работает с ведущими марками гель-лаков: OPI, CND, Gelish. "
        "Мастер сложного дизайна и nail-арта. Любимое направление — минимализм.",
        [
            "Маникюр классический",
            "Маникюр с гель-лаком",
            "Педикюр классический",
            "Педикюр с гель-лаком",
        ],
    ),
    (
        "Катя Смирнова",
        "Парикмахер-стилист",
        3,
        "Катя — парикмахер-стилист с 3-летним опытом. "
        "Специализируется на стрижках и окрашивании. "
        "Прошла обучение в школе Wella и Schwarzkopf. "
        "Поможет подобрать цвет и стрижку под тип лица.",
        [
            "Стрижка женская",
            "Стрижка мужская",
            "Окрашивание однотонное",
            "Мелирование / балаяж",
            "Укладка",
        ],
    ),
    (
        "Анна Козлова",
        "Мастер бровей и ресниц",
        7,
        "Анна — опытный мастер с 7-летним стажем в области оформления бровей и ресниц. "
        "Сертифицированный специалист по ламинированию и наращиванию. "
        "Индивидуально подбирает форму бровей под черты лица.",
        [
            "Коррекция бровей",
            "Окрашивание бровей",
            "Ламинирование ресниц",
            "Наращивание ресниц",
        ],
    ),
]

KNOWLEDGE_DOCS = [
    (
        "Прайс-лист",
        "price",
        """ПРАЙС-ЛИСТ САЛОНА КРАСОТЫ

МАНИКЮР И ПЕДИКЮР (мастер Оля Иванова):
• Маникюр классический — 1 200 руб (60 мин)
• Маникюр с гель-лаком — 1 800 руб (90 мин)
• Педикюр классический — 1 500 руб (75 мин)
• Педикюр с гель-лаком — 2 000 руб (120 мин)

СТРИЖКИ И ОКРАШИВАНИЕ (мастер Катя Смирнова):
• Стрижка женская — от 1 500 руб (60 мин)
• Стрижка мужская — 800 руб (30 мин)
• Окрашивание однотонное — от 3 500 руб (120 мин)
• Мелирование / балаяж — от 5 500 руб (180 мин)
• Укладка — от 1 000 руб (45 мин)

БРОВИ И РЕСНИЦЫ (мастер Анна Козлова):
• Коррекция бровей — 800 руб (30 мин)
• Окрашивание бровей — 600 руб (20 мин)
• Ламинирование ресниц — 2 500 руб (90 мин)
• Наращивание ресниц — от 3 500 руб (150 мин)""",
    ),
    (
        "Часто задаваемые вопросы (FAQ)",
        "faq",
        """ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ

Как записаться?
Напишите нам в Telegram, мы подберём удобное время.

Работаете ли вы в выходные?
Да, работаем ежедневно с 10:00 до 20:00, включая субботу и воскресенье.

Можно ли прийти без записи?
Лучше записаться заранее — мастера часто заняты. Но при наличии свободного окна принимаем.

Есть ли парковка?
Да, бесплатная парковка во дворе здания.

Как отменить запись?
Сообщите нам за 2 часа до записи — и мы без проблем перенесём или отменим.

Принимаете ли оплату картой?
Да, принимаем карты, наличные и переводы по СБП.

Есть ли скидки?
Постоянным клиентам — скидка 10% начиная с третьего визита.
Именинникам — скидка 15% в день рождения и 3 дня после.

Что делать, если не понравился результат?
Сразу сообщите администратору — разберёмся и исправим. Ваш комфорт для нас важен.""",
    ),
    (
        "О мастерах",
        "general",
        """НАШИ МАСТЕРА

Оля Иванова — маникюр и педикюр, 5 лет опыта.
Работает с гель-лаками OPI, CND, Gelish. Специализируется на сложном дизайне и nail-арте.

Катя Смирнова — парикмахер-стилист, 3 года опыта.
Специализируется на стрижках и окрашивании. Обучение в школах Wella и Schwarzkopf.
Поможет подобрать цвет и стрижку под тип лица.

Анна Козлова — брови и ресницы, 7 лет опыта.
Сертифицированный специалист по ламинированию и наращиванию ресниц.
Индивидуально подбирает форму бровей под черты лица.""",
    ),
    (
        "Политика салона",
        "policy",
        """ПОЛИТИКА САЛОНА

Опоздание:
Ждём клиента 15 минут. При опоздании более 15 минут запись может быть перенесена.

Отмена записи:
Просим предупреждать об отмене минимум за 2 часа. Отмена в день записи без предупреждения —
штраф 50% от стоимости услуги при следующем визите.

Дети:
Дети до 12 лет обслуживаются только в сопровождении взрослых.

Аллергии и противопоказания:
Если у вас есть аллергии на косметику или краски — сообщите мастеру до начала процедуры.
Мы проведём тест на аллергическую реакцию.

Гарантия на работу:
На гель-лак — 7 дней. На окрашивание — 14 дней. При возникновении вопросов свяжитесь с нами.""",
    ),
]


class Command(BaseCommand):
    help = "Seed Salon pk=1 with demo data (masters, services, knowledge base, sample bookings)"

    def add_arguments(self, parser):
        parser.add_argument("--salon-id", type=int, default=1)
        parser.add_argument(
            "--clear", action="store_true", help="Delete existing data before seeding"
        )

    def handle(self, *args, **options):
        from apps.salons.models import Salon
        from apps.knowledge_base.models import (
            Service,
            Master,
            KnowledgeDocument,
            Booking,
        )

        salon_id = options["salon_id"]
        try:
            salon = Salon.objects.get(pk=salon_id)
        except Salon.DoesNotExist:
            self.stderr.write(
                f"Salon with id={salon_id} not found. Create it in admin first."
            )
            return

        if options["clear"]:
            Booking.objects.filter(salon=salon).delete()
            Master.objects.filter(salon=salon).delete()
            Service.objects.filter(salon=salon).delete()
            KnowledgeDocument.objects.filter(salon=salon).delete()
            self.stdout.write("Cleared existing data.")

        # --- Services ---
        service_map = {}
        for title, category, duration, price_min, price_max, description in SERVICES:
            svc, created = Service.objects.get_or_create(
                salon=salon,
                title=title,
                defaults={
                    "category": category,
                    "duration_minutes": duration,
                    "price_min": price_min,
                    "price_max": price_max,
                    "description": description,
                    "is_active": True,
                },
            )
            service_map[title] = svc
            if created:
                self.stdout.write(f"  + Service: {title}")

        # --- Masters ---
        for name, specialization, experience, bio, svc_titles in MASTERS:
            master, created = Master.objects.get_or_create(
                salon=salon,
                name=name,
                defaults={
                    "specialization": specialization,
                    "experience_years": experience,
                    "bio": bio,
                    "is_active": True,
                },
            )
            master.services.set(
                [service_map[t] for t in svc_titles if t in service_map]
            )
            if created:
                self.stdout.write(f"  + Master: {name} ({experience} лет)")

        # --- Knowledge documents ---
        for title, doc_type, content in KNOWLEDGE_DOCS:
            doc, created = KnowledgeDocument.objects.get_or_create(
                salon=salon,
                title=title,
                defaults={
                    "document_type": doc_type,
                    "content": content,
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(f"  + Doc: {title}")

        # --- Sample bookings (next 7 days) ---
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        masters = list(Master.objects.filter(salon=salon))
        sample_bookings = [
            (
                "Мария Петрова",
                "+7 (916) 123-45-67",
                "Маникюр с гель-лаком",
                "Оля Иванова",
                1,
            ),
            (
                "Светлана Орлова",
                "+7 (926) 234-56-78",
                "Стрижка женская",
                "Катя Смирнова",
                1,
            ),
            (
                "Елена Волкова",
                "+7 (936) 345-67-89",
                "Коррекция бровей",
                "Анна Козлова",
                2,
            ),
            (
                "Анастасия Новикова",
                "+7 (946) 456-78-90",
                "Педикюр с гель-лаком",
                "Оля Иванова",
                2,
            ),
            (
                "Ирина Кузнецова",
                "+7 (956) 567-89-01",
                "Мелирование / балаяж",
                "Катя Смирнова",
                3,
            ),
        ]

        for client_name, phone, svc_title, master_name, day_offset in sample_bookings:
            if svc_title not in service_map:
                continue
            svc = service_map[svc_title]
            master = next((m for m in masters if m.name == master_name), None)
            starts = (now + timedelta(days=day_offset)).replace(hour=11 + day_offset)
            ends = starts + timedelta(minutes=svc.duration_minutes)
            booking, created = Booking.objects.get_or_create(
                salon=salon,
                client_phone=phone,
                starts_at=starts,
                defaults={
                    "client_name": client_name,
                    "service": svc,
                    "master": master,
                    "ends_at": ends,
                    "status": "confirmed",
                },
            )
            if created:
                self.stdout.write(
                    f"  + Booking: {client_name} → {svc_title} ({starts:%d.%m %H:%M})"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Salon '{salon.name}' seeded with "
                f"{len(SERVICES)} services, {len(MASTERS)} masters, "
                f"{len(KNOWLEDGE_DOCS)} knowledge docs, {len(sample_bookings)} bookings."
            )
        )
