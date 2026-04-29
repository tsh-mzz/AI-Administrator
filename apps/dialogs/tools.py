import structlog
from apps.knowledge_base.retriever import search_knowledge

logger = structlog.get_logger(__name__)

TOOLS_SCHEMA = [
    {
        "name": "search_knowledge_base",
        "description": "Искать ответ в базе знаний салона (FAQ, политики, описания услуг)",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_services",
        "description": "Получить список услуг салона с ценами и длительностью",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Категория услуг (опционально)",
                }
            },
        },
    },
    {
        "name": "get_masters",
        "description": "Получить список мастеров (опционально для конкретной услуги)",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "integer",
                    "description": "ID услуги из get_services",
                }
            },
        },
    },
    {
        "name": "get_available_slots",
        "description": "Получить свободные окна записи на услугу",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "integer"},
                "master_id": {"type": "integer"},
                "date_from": {
                    "type": "string",
                    "description": "YYYY-MM-DD",
                },
                "date_to": {
                    "type": "string",
                    "description": "YYYY-MM-DD",
                },
            },
            "required": ["service_id", "date_from"],
        },
    },
    {
        "name": "create_booking",
        "description": (
            "Создать запись клиента. "
            "ВАЖНО: перед вызовом ОБЯЗАТЕЛЬНО спроси имя и номер телефона клиента — "
            "нельзя вызывать этот инструмент с пустыми client_phone или client_name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "client_phone": {
                    "type": "string",
                    "description": "Номер телефона клиента (обязательно спросить заранее)",
                },
                "client_name": {
                    "type": "string",
                    "description": "Имя клиента (обязательно спросить заранее)",
                },
                "service_id": {"type": "integer"},
                "master_id": {"type": "integer"},
                "datetime": {
                    "type": "string",
                    "description": "ISO 8601 с секундами, например 2026-05-02T14:00:00",
                },
            },
            "required": ["client_phone", "client_name", "service_id", "datetime"],
        },
    },
    {
        "name": "escalate_to_admin",
        "description": "Передать диалог администратору (сложный вопрос, конфликт, нестандартный запрос)",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Причина эскалации"}
            },
            "required": ["reason"],
        },
    },
]


def get_tools_for_salon(salon) -> list:
    return TOOLS_SCHEMA


async def execute_tool(tool_name: str, tool_input: dict, salon, conversation) -> dict:
    logger.info("tool_call", tool=tool_name, input=tool_input, salon_id=salon.id)

    if tool_name == "search_knowledge_base":
        return await _search_knowledge_base(tool_input, salon)

    if tool_name == "get_services":
        return await _get_services(tool_input, salon)

    if tool_name == "get_masters":
        return await _get_masters(tool_input, salon)

    if tool_name == "get_available_slots":
        return await _get_available_slots(tool_input, salon)

    if tool_name == "create_booking":
        return await _create_booking(tool_input, salon, conversation)

    if tool_name == "escalate_to_admin":
        return await _escalate_to_admin(tool_input, salon, conversation)

    return {"error": f"Unknown tool: {tool_name}"}


async def _search_knowledge_base(tool_input: dict, salon) -> dict:
    query = tool_input.get("query", "")
    results = await search_knowledge(salon_id=salon.id, query=query, top_k=3)
    if not results:
        return {"found": False, "message": "Информация не найдена в базе знаний"}
    texts = [r["text"] for r in results]
    return {"found": True, "results": texts}


async def _get_services(tool_input: dict, salon) -> dict:
    from apps.knowledge_base.models import Service

    qs = Service.objects.filter(salon=salon, is_active=True)
    category = tool_input.get("category")
    if category:
        qs = qs.filter(category__icontains=category)
    services = []
    async for s in qs:
        services.append(
            {
                "id": s.yclients_id or s.pk,  # use local pk when no YCLIENTS
                "title": s.title,
                "category": s.category,
                "duration_minutes": s.duration_minutes,
                "price_min": float(s.price_min),
                "price_max": float(s.price_max) if s.price_max else None,
            }
        )
    return {"services": services}


async def _get_masters(tool_input: dict, salon) -> dict:
    from apps.knowledge_base.models import Master

    service_id = tool_input.get("service_id")
    qs = Master.objects.filter(salon=salon, is_active=True)
    if service_id:
        qs = qs.filter(services__pk=service_id) | qs.filter(
            services__yclients_id=service_id
        )
    masters = []
    async for m in qs.distinct():
        masters.append(
            {
                "id": m.yclients_id or m.pk,  # use local pk when no YCLIENTS
                "name": m.name,
                "specialization": m.specialization,
                "experience_years": m.experience_years,
            }
        )
    return {"masters": masters}


async def _get_available_slots(tool_input: dict, salon) -> dict:
    if salon.yclients_company_id and salon.yclients_user_token:
        from apps.integrations.yclients.client import YclientsClient

        client = YclientsClient(
            partner_token=salon.yclients_partner_token or "",
            user_token=salon.yclients_user_token,
        )
        try:
            slots = await client.get_available_slots(
                company_id=salon.yclients_company_id,
                staff_id=tool_input.get("master_id"),
                date=tool_input["date_from"],
            )
            return {"slots": slots}
        except Exception as exc:
            logger.error("yclients_slots_error", error=str(exc))
            return {"slots": [], "error": "Не удалось получить расписание из YCLIENTS"}

    return await _get_local_slots(tool_input, salon)


async def _get_local_slots(tool_input: dict, salon) -> dict:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from apps.knowledge_base.models import Booking, Master, Service

    service_id = tool_input.get("service_id")
    master_id = tool_input.get("master_id")
    date_from_str = tool_input.get("date_from")
    date_to_str = tool_input.get("date_to", date_from_str)

    if not service_id or not date_from_str:
        return {"slots": [], "error": "Укажите услугу и дату"}

    try:
        service = await Service.objects.aget(pk=service_id, salon=salon)
    except Service.DoesNotExist:
        return {"slots": [], "error": "Услуга не найдена"}

    tz = ZoneInfo(salon.timezone)
    date_from = datetime.strptime(date_from_str, "%Y-%m-%d").replace(tzinfo=tz)
    date_to = datetime.strptime(date_to_str, "%Y-%m-%d").replace(tzinfo=tz)

    # Collect masters to check
    if master_id:
        try:
            masters = [await Master.objects.aget(pk=master_id, salon=salon)]
        except Master.DoesNotExist:
            return {"slots": [], "error": "Мастер не найден"}
    else:
        masters = [m async for m in service.masters.filter(salon=salon, is_active=True)]
        if not masters:
            masters = [
                m async for m in Master.objects.filter(salon=salon, is_active=True)
            ]

    # Build working day slots (10:00–19:00, step = service duration)
    step = timedelta(minutes=service.duration_minutes)
    work_start_h, work_end_h = 10, 19
    available = []

    current_day = date_from
    while current_day <= date_to and len(available) < 20:
        slot_start = current_day.replace(
            hour=work_start_h, minute=0, second=0, microsecond=0
        )
        day_end = current_day.replace(
            hour=work_end_h, minute=0, second=0, microsecond=0
        )

        while slot_start + step <= day_end and len(available) < 20:
            slot_end = slot_start + step
            for master in masters:
                conflict = await Booking.objects.filter(
                    master=master,
                    status="confirmed",
                    starts_at__lt=slot_end,
                    ends_at__gt=slot_start,
                ).aexists()
                if not conflict:
                    available.append(
                        {
                            "datetime": slot_start.strftime("%Y-%m-%dT%H:%M"),
                            "master_id": master.pk,
                            "master_name": master.name,
                            "service_id": service.pk,
                            "service_title": service.title,
                            "duration_minutes": service.duration_minutes,
                            "price": str(service.price_min),
                        }
                    )
                    break  # one free master per slot is enough
            slot_start += step

        current_day += timedelta(days=1)

    return {"slots": available, "total_found": len(available)}


async def _create_booking(tool_input: dict, salon, conversation) -> dict:
    if salon.yclients_company_id and salon.yclients_user_token:
        from apps.integrations.yclients.booking import create_yclients_booking

        try:
            result = await create_yclients_booking(salon=salon, booking_data=tool_input)
            return {"success": True, "booking_id": result.get("id")}
        except Exception as exc:
            logger.error("yclients_booking_error", error=str(exc))
            return {"success": False, "error": "Не удалось создать запись в YCLIENTS"}

    return await _create_local_booking(tool_input, salon, conversation)


async def _create_local_booking(tool_input: dict, salon, conversation) -> dict:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from apps.knowledge_base.models import Booking, Master, Service

    client_phone = tool_input.get("client_phone", "")
    client_name = tool_input.get("client_name", "")
    service_id = tool_input.get("service_id")
    master_id = tool_input.get("master_id")
    dt_str = tool_input.get("datetime", "")

    if not all([client_phone, service_id, dt_str]):
        return {
            "success": False,
            "error": "Не хватает данных: нужен телефон, услуга и дата/время",
        }

    try:
        service = await Service.objects.aget(pk=service_id, salon=salon)
    except Service.DoesNotExist:
        return {"success": False, "error": "Услуга не найдена"}

    master = None
    if master_id:
        try:
            master = await Master.objects.aget(pk=master_id, salon=salon)
        except Master.DoesNotExist:
            return {"success": False, "error": "Мастер не найден"}

    tz = ZoneInfo(salon.timezone)
    try:
        starts_at = (
            datetime.fromisoformat(dt_str).replace(tzinfo=tz)
            if "+" not in dt_str
            else datetime.fromisoformat(dt_str)
        )
    except ValueError:
        return {
            "success": False,
            "error": f"Неверный формат даты: {dt_str}. Используй ISO 8601, например 2026-05-02T14:00",
        }

    ends_at = starts_at + timedelta(minutes=service.duration_minutes)

    # Check conflict
    if master:
        conflict = await Booking.objects.filter(
            master=master,
            status="confirmed",
            starts_at__lt=ends_at,
            ends_at__gt=starts_at,
        ).aexists()
        if conflict:
            return {
                "success": False,
                "error": "Это время уже занято у мастера. Предложи другое время через get_available_slots.",
            }

    booking = await Booking.objects.acreate(
        salon=salon,
        client_name=client_name,
        client_phone=client_phone,
        service=service,
        master=master,
        starts_at=starts_at,
        ends_at=ends_at,
        status="confirmed",
        conversation=conversation,
    )

    logger.info("local_booking_created", booking_id=booking.pk, salon_id=salon.id)
    return {
        "success": True,
        "booking_id": booking.pk,
        "summary": f"{service.title} {starts_at.strftime('%d.%m.%Y в %H:%M')}",
        "master": master.name if master else "любой свободный",
    }


async def _escalate_to_admin(tool_input: dict, salon, conversation) -> dict:
    reason = tool_input.get("reason", "")

    await conversation.__class__.objects.filter(pk=conversation.pk).aupdate(
        status="handed_to_admin",
        escalation_reason=reason,
    )

    # Notify admin in Telegram
    if salon.admin_telegram_id:
        try:
            from apps.integrations.telegram.client import TelegramClient

            client = TelegramClient(token=salon.telegram_bot_token)
            text = (
                f"⚠️ Эскалация диалога!\n"
                f"Канал: {conversation.channel}\n"
                f"Chat ID: {conversation.external_chat_id}\n"
                f"Причина: {reason}"
            )
            await client.send_message(chat_id=salon.admin_telegram_id, text=text)
        except Exception as exc:
            logger.error("escalation_notify_error", error=str(exc))

    return {"escalated": True, "message": "Передано администратору"}
