"""POST /orders/{order_id}/discord-ack - Discord button settlement ack."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.models import DiscordUser
from industry.endpoints.loyalty.auth_helpers import can_manage_buyback
from industry.endpoints.loyalty.schemas import (
    DiscordAckLoyaltyMarketOrderRequest,
    LoyaltyMarketOrderResponse,
)
from industry.endpoints.loyalty.serialization import market_order_response
from industry.helpers.lp_market_orders import (
    LpMarketOrderError,
    discord_ack_order,
    expected_ack_user,
)
from industry.models import IndustryLoyaltyPointMarketOrder

PATH = "/orders/{order_id}/discord-ack"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Acknowledge LP/ISK settlement from a Discord button",
    "auth": AuthBearer(),
    "response": {
        200: LoyaltyMarketOrderResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_order_discord_ack(
    request,
    order_id: int,
    payload: DiscordAckLoyaltyMarketOrderRequest,
):
    order = (
        IndustryLoyaltyPointMarketOrder.objects.select_related(
            "loyalty_point", "created_by", "claimed_by"
        )
        .prefetch_related("claims__claimed_by")
        .filter(pk=order_id)
        .first()
    )
    if not order:
        return 404, ErrorResponse(detail="Order not found.")

    discord_user = (
        DiscordUser.objects.filter(id=payload.discord_user_id)
        .select_related("user")
        .first()
    )
    if not discord_user:
        return 403, ErrorResponse(detail="Unknown Discord user.")

    actor = discord_user.user
    action = (payload.action or "").strip().lower()
    try:
        expected = expected_ack_user(order, action)
    except LpMarketOrderError as exc:
        return 400, ErrorResponse(detail=str(exc))

    is_expected = expected is not None and actor.pk == expected.pk
    if not is_expected and not can_manage_buyback(actor):
        return 403, ErrorResponse(detail="Not authorized for this ack.")

    requester = request.user
    if requester.pk != actor.pk and not (
        requester.is_staff or requester.is_superuser
    ):
        return 403, ErrorResponse(detail="Not authorized for this ack.")

    try:
        order = discord_ack_order(order, action=action)
    except LpMarketOrderError as exc:
        return 400, ErrorResponse(detail=str(exc))

    order = (
        IndustryLoyaltyPointMarketOrder.objects.select_related(
            "loyalty_point", "created_by", "claimed_by"
        )
        .prefetch_related("claims__claimed_by")
        .get(pk=order.pk)
    )
    return 200, market_order_response(order)
