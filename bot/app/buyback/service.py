from app.order_ack import DiscordAckError  # noqa: F401
from app.order_ack import DiscordAckResponse
from app.order_ack import discord_ack_order as _discord_ack_order

from .api import BUYBACK_BASE_URL


def discord_ack_order(
    order_id: int, *, action: str, discord_user_id: int
) -> DiscordAckResponse:
    return _discord_ack_order(
        BUYBACK_BASE_URL,
        order_id,
        action=action,
        discord_user_id=discord_user_id,
    )
