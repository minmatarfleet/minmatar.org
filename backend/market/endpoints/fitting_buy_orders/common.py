"""Shared helpers for fitting buy order endpoints."""

from __future__ import annotations

from app.errors import ErrorResponse
from market.models.fitting_buy_order import FittingBuyOrder


def get_order_or_404(order_id: int):
    order = (
        FittingBuyOrder.objects.select_related("owner")
        .filter(pk=order_id)
        .first()
    )
    if order is None:
        return None, (
            404,
            ErrorResponse(detail="Fitting buy order not found."),
        )
    return order, None


def require_owner(request, order: FittingBuyOrder):
    user = request.user
    if user.id == order.owner_id or user.is_staff:
        return None
    return 403, ErrorResponse(
        detail="Only the order owner can modify this order."
    )
