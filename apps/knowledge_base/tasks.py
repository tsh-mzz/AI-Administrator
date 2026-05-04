import asyncio
import datetime
import gzip
import io
import os

import structlog
from config.celery import app

logger = structlog.get_logger(__name__)


@app.task(name="apps.knowledge_base.tasks.send_booking_reminders")
def send_booking_reminders() -> dict:
    """Send reminder messages to clients with bookings tomorrow."""

    async def _run():
        from zoneinfo import ZoneInfo
        from apps.knowledge_base.models import Booking
        from apps.salons.models import Salon

        sent = 0
        failed = 0

        async for salon in Salon.objects.filter(is_active=True):
            tz = ZoneInfo(salon.timezone)
            now = datetime.datetime.now(tz)
            tomorrow_start = (now + datetime.timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            tomorrow_end = tomorrow_start + datetime.timedelta(days=1)

            async for booking in Booking.objects.filter(
                salon=salon,
                status="confirmed",
                reminder_sent=False,
                starts_at__gte=tomorrow_start,
                starts_at__lt=tomorrow_end,
            ).select_related("service", "master", "conversation"):
                try:
                    await _send_reminder(booking, salon)
                    await Booking.objects.filter(pk=booking.pk).aupdate(reminder_sent=True)
                    sent += 1
                except Exception as exc:
                    logger.error(
                        "reminder_send_failed",
                        booking_id=booking.pk,
                        error=str(exc),
                    )
                    failed += 1

        logger.info("reminders_done", sent=sent, failed=failed)
        return {"sent": sent, "failed": failed}

    return asyncio.run(_run())


async def _send_reminder(booking, salon) -> None:
    from apps.integrations.telegram.client import TelegramClient

    master_str = booking.master.name if booking.master else "любым свободным мастером"
    time_str = booking.starts_at.strftime("%d.%m.%Y в %H:%M")
    text = (
        f"👋 Напоминаем о вашей записи!\n\n"
        f"📅 {time_str}\n"
        f"💅 Услуга: {booking.service.title}\n"
        f"👩‍🎨 Мастер: {master_str}\n\n"
        f"Ждём вас! Если хотите отменить или перенести — напишите нам."
    )

    conversation = booking.conversation
    if not conversation:
        return

    channel = conversation.channel

    if channel == "telegram" and salon.telegram_bot_token:
        client = TelegramClient(token=salon.telegram_bot_token)
        await client.send_message(
            chat_id=conversation.external_chat_id,
            text=text,
        )
    elif channel == "max" and salon.max_bot_token:
        from apps.integrations.max.client import MaxClient
        client = MaxClient(token=salon.max_bot_token)
        await client.send_message(
            chat_id=conversation.external_chat_id,
            text=text,
        )


@app.task
def index_document_task(document_id: int) -> None:
    from apps.knowledge_base.models import KnowledgeDocument
    from apps.knowledge_base.indexer import index_document

    async def _run():
        doc = await KnowledgeDocument.objects.select_related("salon").aget(
            pk=document_id
        )
        await index_document(doc)

    asyncio.run(_run())


@app.task(name="apps.knowledge_base.tasks.backup_database_task")
def backup_database_task() -> dict:
    from django.core.management import call_command

    backup_dir = "/app/backups"
    os.makedirs(backup_dir, exist_ok=True)
    date_str = datetime.date.today().isoformat()
    filename = f"{backup_dir}/db_{date_str}.json.gz"

    buf = io.StringIO()
    call_command("dumpdata", "--natural-foreign", "--natural-primary", stdout=buf)

    with gzip.open(filename, "wt", encoding="utf-8") as f:
        f.write(buf.getvalue())

    size_kb = os.path.getsize(filename) // 1024
    logger.info("backup_complete", file=filename, size_kb=size_kb)
    return {"file": filename, "size_kb": size_kb}
