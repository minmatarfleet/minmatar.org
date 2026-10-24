from app.order_ack import DiscordAckRequest, DiscordAckResponse  # noqa: F401
from app.settings import settings

BUYBACK_BASE_URL = f"{settings.API_URL}/buyback/stock"
