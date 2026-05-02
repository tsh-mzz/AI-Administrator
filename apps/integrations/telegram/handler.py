import structlog
from apps.integrations.base import ChannelHandler
from apps.integrations.telegram.client import TelegramClient

logger = structlog.get_logger(__name__)


class TelegramHandler(ChannelHandler):

    async def handle_incoming_update(self, update: dict, salon) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        text = message.get("text", "").strip()

        if not text:
            voice = message.get("voice") or message.get("audio")
            if voice:
                text = await self._transcribe_voice(voice, salon)
                if not text:
                    await self.send_message(
                        salon=salon,
                        external_chat_id=str(message["chat"]["id"]),
                        text="Не удалось распознать голосовое сообщение. Пожалуйста, напишите текстом 🙏",
                    )
                    return
            else:
                await self.send_message(
                    salon=salon,
                    external_chat_id=str(message["chat"]["id"]),
                    text="Пожалуйста, напишите ваш вопрос текстом 🙏",
                )
                return

        chat_id = str(message["chat"]["id"])
        from_user = message.get("from", {})
        user_name = " ".join(filter(None, [
            from_user.get("first_name", ""),
            from_user.get("last_name", ""),
        ])) or from_user.get("username", "")

        conversation = await self._get_or_create_conversation(
            salon=salon, chat_id=chat_id, user_name=user_name
        )

        # Check if handed to admin — don't auto-reply
        if conversation.status == "handed_to_admin":
            return

        from apps.dialogs.tasks import process_message_task
        process_message_task.delay(conversation.id, text)

        logger.info("telegram_message_queued", chat_id=chat_id, salon_id=salon.id)

    async def send_message(self, salon, external_chat_id: str, text: str) -> None:
        client = TelegramClient(token=salon.telegram_bot_token)
        await client.send_message(chat_id=external_chat_id, text=text)

    async def _transcribe_voice(self, voice: dict, salon) -> str:
        try:
            from django.conf import settings
            import openai
            from apps.integrations.telegram.client import TelegramClient

            file_id = voice.get("file_id")
            if not file_id:
                return ""

            tg_client = TelegramClient(token=salon.telegram_bot_token)
            audio_bytes = await tg_client.download_file(file_id)

            oai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            import io
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "voice.ogg"

            transcript = await oai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru",
            )
            text = transcript.text.strip()
            logger.info("voice_transcribed", salon_id=salon.id, length=len(text))
            return text
        except Exception as exc:
            logger.error("voice_transcription_error", error=str(exc), salon_id=salon.id)
            return ""

    async def _get_or_create_conversation(self, salon, chat_id: str, user_name: str):
        from apps.dialogs.models import Conversation
        conversation, created = await Conversation.objects.aget_or_create(
            salon=salon,
            channel="telegram",
            external_chat_id=chat_id,
            defaults={"context_json": {"user_name": user_name}},
        )
        if created:
            logger.info("conversation_created", channel="telegram", chat_id=chat_id, salon_id=salon.id)
        return conversation
