from pydantic import BaseModel

from app.settings import settings

NOTIFICATIONS_BASE_URL = f"{settings.API_URL}/notifications"


class AckDeliveryRequest(BaseModel):
    discord_user_id: int


class AckDeliveryResponse(BaseModel):
    id: int
    status: str
    delete_message: bool = True
