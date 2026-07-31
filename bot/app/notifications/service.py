import logging

import requests

from app.settings import settings

from .api import (
    NOTIFICATIONS_BASE_URL,
    AckDeliveryRequest,
    AckDeliveryResponse,
)

logger = logging.getLogger(__name__)

AUTH_HEADERS = {"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"}


def ack_delivery(
    delivery_id: int, discord_user_id: int
) -> AckDeliveryResponse:
    response = requests.post(
        f"{NOTIFICATIONS_BASE_URL}/deliveries/{delivery_id}/ack",
        headers=AUTH_HEADERS,
        json=AckDeliveryRequest(discord_user_id=discord_user_id).model_dump(),
        timeout=10,
    )
    response.raise_for_status()
    return AckDeliveryResponse.model_validate(response.json())
