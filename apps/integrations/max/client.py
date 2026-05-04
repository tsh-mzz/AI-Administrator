import httpx
import structlog

logger = structlog.get_logger(__name__)

MAX_API = "https://botapi.max.ru"


class MaxClient:
    def __init__(self, token: str):
        self.token = token

    def _url(self, method: str) -> str:
        return f"{MAX_API}/{method}"

    async def send_message(self, chat_id: str | int, text: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self._url("messages"),
                params={"access_token": self.token},
                json={
                    "recipient": {"chat_id": str(chat_id)},
                    "type": "text",
                    "text": text,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def set_webhook(self, url: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self._url("subscriptions"),
                params={"access_token": self.token},
                json={"url": url, "update_types": ["message_created"]},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_me(self) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                self._url("me"),
                params={"access_token": self.token},
            )
            resp.raise_for_status()
            return resp.json()
