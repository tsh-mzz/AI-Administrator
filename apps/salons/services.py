from .models import Salon


async def get_salon_by_id(salon_id: int) -> Salon:
    return await Salon.objects.aget(pk=salon_id, is_active=True)
