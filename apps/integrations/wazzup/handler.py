import structlog
from apps.integrations.base import ChannelHandler
from apps.integrations.wazzup.client import WazzupClient

logger = structlog.get_logger(__name__)


class WazzupHandler(ChannelHandler):
    """Handles both WhatsApp and Instagram via Wazzup24."""

    async def handle_incoming_update(self, update: dict, salon) -> None:
        messages = update.get("messages", [])
        for msg in messages:
            await self._handle_one(msg, salon)

    async def _handle_one(self, msg: dict, salon) -> None:
        msg_type = msg.get("type")
        if msg_type != "text":
            chat_id = msg.get("chatId", "")
            channel = self._detect_channel(msg, salon)
            await self.send_message(salon=salon, external_chat_id=chat_id, text="Пожалуйста, напишите текстом 🙏", channel=channel)
            return

        chat_id = msg.get("chatId", "")
        text = msg.get("text", "").strip()
        channel = self._detect_channel(msg, salon)

        conversation = await self._get_or_create_conversation(salon, chat_id, channel)
        if conversation.status == "handed_to_admin":
            return

        from apps.dialogs.tasks import process_message_task
        process_message_task.delay(conversation.id, text)

    def _detect_channel(self, msg: dict, salon) -> str:
        channel_id = msg.get("channelId", "")
        if channel_id == salon.wazzup_channel_id_instagram:
            return "instagram"
        return "whatsapp"

    async def send_message(self, salon, external_chat_id: str, text: str, channel: str = "whatsapp") -> None:
        channel_id = (
            salon.wazzup_channel_id_instagram
            if channel == "instagram"
            else salon.wazzup_channel_id_whatsapp
        )
        client = WazzupClient(api_key=salon.wazzup_api_key)
        await client.send_message(channel_id=channel_id, chat_id=external_chat_id, text=text)

    async def _get_or_create_conversation(self, salon, chat_id: str, channel: str):
        from apps.dialogs.models import Conversation
        conversation, created = await Conversation.objects.aget_or_create(
            salon=salon,
            channel=channel,
            external_chat_id=chat_id,
            defaults={},
        )
        return conversation
