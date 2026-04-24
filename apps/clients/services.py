from .models import SalonClient


async def get_or_create_client(salon, phone: str, name: str = "") -> SalonClient:
    client, _ = await SalonClient.objects.aget_or_create(
        salon=salon,
        phone=phone,
        defaults={"name": name},
    )
    return client
