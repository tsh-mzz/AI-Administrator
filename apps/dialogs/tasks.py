import structlog
from asgiref.sync import async_to_sync
from config.celery import app

logger = structlog.get_logger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=5)
def process_message_task(self, conversation_id: int, user_message: str):
    """Celery task: run AI engine and send reply back to the user."""
    from apps.dialogs.models import Conversation
    from apps.dialogs.ai_engine import process_incoming_message

    async def _run():
        conversation = await Conversation.objects.select_related("salon").aget(
            pk=conversation_id
        )
        response = await process_incoming_message(conversation, user_message)
        await _send_reply(conversation, response.text)
        return response

    async def _send_reply(conversation, text: str):
        salon = conversation.salon
        channel = conversation.channel
        chat_id = conversation.external_chat_id

        if channel == "telegram":
            from apps.integrations.telegram.client import TelegramClient
            client = TelegramClient(token=salon.telegram_bot_token)
            await client.send_message(chat_id=chat_id, text=text)

        elif channel in ("whatsapp", "instagram"):
            from apps.integrations.wazzup.client import WazzupClient
            channel_id = (
                salon.wazzup_channel_id_instagram
                if channel == "instagram"
                else salon.wazzup_channel_id_whatsapp
            )
            client = WazzupClient(api_key=salon.wazzup_api_key)
            await client.send_message(channel_id=channel_id, chat_id=chat_id, text=text)

    try:
        response = async_to_sync(_run)()
        logger.info(
            "message_processed",
            conversation_id=conversation_id,
            latency_ms=response.latency_ms,
            cost_usd=str(response.cost_usd),
        )
        return {"text": response.text, "escalated": response.escalate}
    except Exception as exc:
        logger.error(
            "process_message_task_error",
            error=str(exc),
            conversation_id=conversation_id,
        )
        raise self.retry(exc=exc)
