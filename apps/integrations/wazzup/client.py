import httpx
import structlog

logger = structlog.get_logger(__name__)

WAZZUP_API = "https://api.wazzup24.com/v3"


class WazzupClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def send_message(self, channel_id: str, chat_id: str, text: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{WAZZUP_API}/message",
                headers=self._headers(),
                json={"channelId": channel_id, "chatId": chat_id, "text": text},
            )
            resp.raise_for_status()
            return resp.json()
