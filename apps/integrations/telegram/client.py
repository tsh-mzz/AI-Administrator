import httpx
import structlog

logger = structlog.get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramClient:
    def __init__(self, token: str):
        self.token = token

    def _url(self, method: str) -> str:
        return TELEGRAM_API.format(token=self.token, method=method)

    async def send_message(self, chat_id: str | int, text: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self._url("sendMessage"),
                json={"chat_id": chat_id, "text": text},
            )
            resp.raise_for_status()
            return resp.json()

    async def set_webhook(self, url: str, secret_token: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self._url("setWebhook"),
                json={"url": url, "secret_token": secret_token},
            )
            resp.raise_for_status()
            return resp.json()
