import json
import structlog
from apps.knowledge_base.retriever import search_knowledge

logger = structlog.get_logger(__name__)

TOOLS_SCHEMA = [
    {
        "name": "search_knowledge_base",
        "description": "Искать ответ в базе знаний салона (FAQ, политики, описания услуг)",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Поисковый запрос"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_services",
        "description": "Получить список услуг салона с ценами и длительностью",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Категория услуг (опционально)"}
            },
        },
    },
    {
        "name": "get_masters",
        "description": "Получить список мастеров (опционально для конкретной услуги)",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "integer", "description": "ID услуги из get_services"}
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
                "date_from": {"type": "string", "format": "date", "description": "YYYY-MM-DD"},
                "date_to": {"type": "string", "format": "date", "description": "YYYY-MM-DD"},
            },
            "required": ["service_id", "date_from"],
        },
    },
    {
        "name": "create_booking",
        "description": "Создать запись клиента на услугу после подтверждения всех данных",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_phone": {"type": "string"},
                "client_name": {"type": "string"},
                "service_id": {"type": "integer"},
                "master_id": {"type": "integer"},
                "datetime": {"type": "string", "format": "date-time", "description": "ISO 8601"},
            },
            "required": ["client_phone", "service_id", "datetime"],
        },
    },
    {
        "name": "escalate_to_admin",
        "description": "Передать диалог администратору (сложный вопрос, конфликт, нестандартный запрос)",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string", "description": "Причина эскалации"}},
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
        services.append({
            "id": s.yclients_id,
            "title": s.title,
            "category": s.category,
            "duration_minutes": s.duration_minutes,
            "price_min": float(s.price_min),
            "price_max": float(s.price_max) if s.price_max else None,
        })
    if not services:
        return {
            "services": [],
            "note": "CRM не подключён. Используй search_knowledge_base чтобы найти информацию о ценах и услугах.",
        }
    return {"services": services}


async def _get_masters(tool_input: dict, salon) -> dict:
    from apps.knowledge_base.models import Master
    qs = Master.objects.filter(salon=salon, is_active=True)
    service_id = tool_input.get("service_id")
    masters = []
    async for m in qs:
        if service_id and service_id not in m.service_ids:
            continue
        masters.append({
            "id": m.yclients_id,
            "name": m.name,
            "specialization": m.specialization,
        })
    return {"masters": masters}


async def _get_available_slots(tool_input: dict, salon) -> dict:
    # Real implementation calls YCLIENTS; stub for Week 1
    from apps.integrations.yclients.client import YclientsClient
    if not salon.yclients_company_id or not salon.yclients_user_token:
        return {"slots": [], "note": "YCLIENTS не подключён — запись через администратора"}

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
        return {"slots": [], "error": "Не удалось получить расписание"}


async def _create_booking(tool_input: dict, salon, conversation) -> dict:
    from apps.integrations.yclients.booking import create_yclients_booking
    if not salon.yclients_company_id or not salon.yclients_user_token:
        return {"success": False, "note": "YCLIENTS не подключён — передаю администратору"}

    try:
        result = await create_yclients_booking(salon=salon, booking_data=tool_input)
        return {"success": True, "booking_id": result.get("id")}
    except Exception as exc:
        logger.error("yclients_booking_error", error=str(exc))
        return {"success": False, "error": "Не удалось создать запись"}


async def _escalate_to_admin(tool_input: dict, salon, conversation) -> dict:
    from django.utils import timezone
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
