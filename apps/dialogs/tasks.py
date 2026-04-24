import asyncio
import structlog
from config.celery import app

logger = structlog.get_logger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=5)
def process_message_task(self, conversation_id: int, user_message: str):
    """Celery task: run AI engine for one incoming message."""
    from apps.dialogs.models import Conversation
    from apps.dialogs.ai_engine import process_incoming_message

    async def _run():
        conversation = await Conversation.objects.select_related("salon").aget(pk=conversation_id)
        response = await process_incoming_message(conversation, user_message)
        return response

    try:
        response = asyncio.run(_run())
        logger.info(
            "message_processed",
            conversation_id=conversation_id,
            latency_ms=response.latency_ms,
            cost_usd=str(response.cost_usd),
        )
        return {"text": response.text, "escalated": response.escalate}
    except Exception as exc:
        logger.error("process_message_task_error", error=str(exc), conversation_id=conversation_id)
        raise self.retry(exc=exc)
