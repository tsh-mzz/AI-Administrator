import asyncio
import structlog
from config.celery import app

logger = structlog.get_logger(__name__)


@app.task
def sync_services_for_all_salons():
    from apps.salons.models import Salon
    for salon in Salon.objects.filter(is_active=True, yclients_company_id__isnull=False):
        sync_services_for_salon.delay(salon.id)


@app.task
def sync_masters_for_all_salons():
    from apps.salons.models import Salon
    for salon in Salon.objects.filter(is_active=True, yclients_company_id__isnull=False):
        sync_masters_for_salon.delay(salon.id)


@app.task
def sync_clients_for_all_salons():
    pass  # Implemented in Week 2


@app.task
def sync_services_for_salon(salon_id: int):
    from apps.salons.models import Salon
    from apps.knowledge_base.models import Service
    from apps.integrations.yclients.client import YclientsClient

    async def _run():
        salon = await Salon.objects.aget(pk=salon_id)
        client = YclientsClient(
            partner_token=salon.yclients_partner_token or "",
            user_token=salon.yclients_user_token or "",
        )
        services = await client.get_services(salon.yclients_company_id)
        for s in services:
            await Service.objects.aupdate_or_create(
                salon=salon,
                yclients_id=s["id"],
                defaults={
                    "title": s.get("title", ""),
                    "category": s.get("category", {}).get("title", ""),
                    "duration_minutes": s.get("duration", 60),
                    "price_min": s.get("price_min", 0),
                    "price_max": s.get("price_max"),
                    "is_active": True,
                },
            )
        logger.info("services_synced", salon_id=salon_id, count=len(services))

    asyncio.run(_run())


@app.task
def sync_masters_for_salon(salon_id: int):
    from apps.salons.models import Salon
    from apps.knowledge_base.models import Master
    from apps.integrations.yclients.client import YclientsClient

    async def _run():
        salon = await Salon.objects.aget(pk=salon_id)
        client = YclientsClient(
            partner_token=salon.yclients_partner_token or "",
            user_token=salon.yclients_user_token or "",
        )
        staff = await client.get_staff(salon.yclients_company_id)
        for m in staff:
            master, _ = await Master.objects.aupdate_or_create(
                salon=salon,
                yclients_id=m["id"],
                defaults={
                    "name": m.get("name", ""),
                    "specialization": m.get("specialization", ""),
                    "is_active": True,
                },
            )
            yclients_service_ids = [s["id"] for s in m.get("services", [])]
            if yclients_service_ids:
                from apps.knowledge_base.models import Service
                services = Service.objects.filter(
                    salon=salon, yclients_id__in=yclients_service_ids
                )
                await master.services.aset(services)
        logger.info("masters_synced", salon_id=salon_id, count=len(staff))

    asyncio.run(_run())
