"""POST /stock/orders/{order_id}/discord-ack — Discord button settlement."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from buyback.endpoints.purchase.serialization import order_response
from buyback.endpoints.schemas import (
    BuybackPurchaseDiscordAckRequest,
    BuybackPurchaseOrderResponse,
)
from buyback.helpers.auth import can_manage_stock_sales
from buyback.helpers.purchase_orders import (
    PurchaseOrderError,
    discord_ack_order,
)
from buyback.models import BuybackPurchaseOrder
from discord.models import DiscordUser

PATH = "/orders/{order_id}/discord-ack"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Acknowledge hangar purchase Complete/Cancel from Discord",
    "auth": AuthBearer(),
    "response": {
        200: BuybackPurchaseOrderResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def _actor_may_ack(order: BuybackPurchaseOrder, actor, action: str) -> bool:
    if action == "complete":
        return can_manage_stock_sales(actor)
    if action == "cancel":
        is_owner = order.created_by_id == actor.pk
        return is_owner or can_manage_stock_sales(actor)
    return False


def post_order_discord_ack(
    request,
    order_id: int,
    payload: BuybackPurchaseDiscordAckRequest,
):
    order = (
        BuybackPurchaseOrder.objects.select_related(
            "created_by", "completed_by"
        )
        .prefetch_related("lines")
        .filter(pk=order_id)
        .first()
    )
    if order is None:
        return 404, ErrorResponse(detail="Purchase order not found.")

    discord_user = (
        DiscordUser.objects.filter(id=payload.discord_user_id)
        .select_related("user")
        .first()
    )
    if not discord_user:
        return 403, ErrorResponse(detail="Unknown Discord user.")

    actor = discord_user.user
    action = (payload.action or "").strip().lower()
    if action not in ("complete", "cancel"):
        return 400, ErrorResponse(detail="Unknown Discord ack action.")
    if not _actor_may_ack(order, actor, action):
        return 403, ErrorResponse(detail="Not authorized for this ack.")

    requester = request.user
    if requester.pk != actor.pk and not (
        requester.is_staff or requester.is_superuser
    ):
        return 403, ErrorResponse(detail="Not authorized for this ack.")

    try:
        order = discord_ack_order(order, action=action, actor=actor)
    except PurchaseOrderError as exc:
        return 400, ErrorResponse(detail=str(exc))

    order = (
        BuybackPurchaseOrder.objects.prefetch_related("lines")
        .select_related("created_by", "completed_by")
        .get(pk=order.pk)
    )
    return 200, order_response(order)
