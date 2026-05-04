import structlog
from apps.integrations.base import ChannelHandler
from apps.integrations.max.client import MaxClient

logger = structlog.get_logger(__name__)


class MaxHandler(ChannelHandler):

    async def handle_incoming_update(self, update: dict, salon) -> None:
        for item in update.get("updates", []):
            if item.get("type") != "message_created":
                continue
            await self._handle_message(item.get("message", {}), salon)

    async def _handle_message(self, message: dict, salon) -> None:
        body = message.get("body", {})
        text = (body.get("text") or "").strip()

        sender = message.get("sender", {})
        recipient = message.get("recipient", {})
        chat_id = str(recipient.get("chat_id") or sender.get("user_id", ""))

        if not chat_id:
            return

        if not text:
            await self.send_message(
                salon=salon,
                external_chat_id=chat_id,
                text="Пожалуйста, напишите ваш вопрос текстом 🙏",
            )
            return

        user_name = sender.get("name", "") or sender.get("username", "")

        conversation = await self._get_or_create_conversation(
            salon=salon, chat_id=chat_id, user_name=user_name
        )

        if conversation.status == "handed_to_admin":
            return

        from apps.dialogs.tasks import process_message_task
        process_message_task.delay(conversation.id, text)

        logger.info("max_message_queued", chat_id=chat_id, salon_id=salon.id)

    async def send_message(self, salon, external_chat_id: str, text: str) -> None:
        client = MaxClient(token=salon.max_bot_token)
        await client.send_message(chat_id=external_chat_id, text=text)

    async def _get_or_create_conversation(self, salon, chat_id: str, user_name: str):
        from apps.dialogs.models import Conversation
        conversation, created = await Conversation.objects.aget_or_create(
            salon=salon,
            channel="max",
            external_chat_id=chat_id,
            defaults={"context_json": {"user_name": user_name}},
        )
        if created:
            logger.info("conversation_created", channel="max", chat_id=chat_id, salon_id=salon.id)
        return conversation
