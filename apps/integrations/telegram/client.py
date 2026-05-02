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

    async def get_file_url(self, file_id: str) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self._url("getFile"), params={"file_id": file_id})
            resp.raise_for_status()
            file_path = resp.json()["result"]["file_path"]
            return f"https://api.telegram.org/file/bot{self.token}/{file_path}"

    async def download_file(self, file_id: str) -> bytes:
        url = await self.get_file_url(file_id)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    async def set_webhook(self, url: str, secret_token: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self._url("setWebhook"),
                json={"url": url, "secret_token": secret_token},
            )
            resp.raise_for_status()
            return resp.json()
