import asyncio
import httpx
import structlog

logger = structlog.get_logger(__name__)

BASE_URL = "https://api.yclients.com/api/v1"


class YclientsClient:
    def __init__(self, partner_token: str, user_token: str = ""):
        self.partner_token = partner_token
        self.user_token = user_token

    def _headers(self) -> dict:
        auth = f"Bearer {self.partner_token}"
        if self.user_token:
            auth += f", User {self.user_token}"
        return {"Authorization": auth, "Accept": "application/vnd.yclients.v2+json"}

    async def _get(self, path: str, params: dict = None) -> dict:
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(f"{BASE_URL}{path}", headers=self._headers(), params=params)
                    if resp.status_code == 429:
                        wait = 2 ** attempt
                        logger.warning("yclients_rate_limit", attempt=attempt, wait=wait)
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPError as exc:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        return {}

    async def _post(self, path: str, body: dict) -> dict:
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(f"{BASE_URL}{path}", headers=self._headers(), json=body)
                    if resp.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPError as exc:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        return {}

    async def get_services(self, company_id: int) -> list[dict]:
        data = await self._get(f"/book_services/{company_id}")
        return data.get("data", [])

    async def get_staff(self, company_id: int) -> list[dict]:
        data = await self._get(f"/book_staff/{company_id}")
        return data.get("data", [])

    async def get_available_slots(self, company_id: int, staff_id: int | None, date: str) -> list[dict]:
        params = {}
        if staff_id:
            params["staff_id"] = staff_id
        data = await self._get(f"/book_times/{company_id}/{staff_id or 0}/{date}", params=params)
        return data.get("data", [])

    async def create_booking(self, company_id: int, booking_data: dict) -> dict:
        data = await self._post(f"/book_record/{company_id}", booking_data)
        return data.get("data", {})
