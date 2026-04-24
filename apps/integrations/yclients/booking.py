from .client import YclientsClient


async def create_yclients_booking(salon, booking_data: dict) -> dict:
    client = YclientsClient(
        partner_token=salon.yclients_partner_token or "",
        user_token=salon.yclients_user_token or "",
    )
    payload = {
        "phone": booking_data["client_phone"],
        "fullname": booking_data.get("client_name", ""),
        "appointments": [
            {
                "id": 1,
                "services": [booking_data["service_id"]],
                "staff_id": booking_data.get("master_id"),
                "datetime": booking_data["datetime"],
            }
        ],
    }
    return await client.create_booking(company_id=salon.yclients_company_id, booking_data=payload)
