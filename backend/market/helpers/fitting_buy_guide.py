"""Guided workflow helpers for fitting buy orders.

Guide step is derived from order state — not stored in the database.
"""

from __future__ import annotations

from market.helpers.fitting_buy_allocations import effective_buy_map
from market.helpers.fitting_buy_plan import ShoppingPlan, build_shopping_plan
from market.models.fitting_buy_order import (
    FittingBuyGuideStep,
    FittingBuyOrder,
    FittingBuyOrderStatus,
)


def _plan(order: FittingBuyOrder, plan: ShoppingPlan | None) -> ShoppingPlan:
    return plan if plan is not None else build_shopping_plan(order)


def order_blocking_short_count(
    order: FittingBuyOrder, plan: ShoppingPlan | None = None
) -> int:
    """How many shopping types are still short in Jita (need swap/allocate)."""
    shopping = _plan(order, plan)
    effective_buy = effective_buy_map(order, shopping)
    count = 0
    items = {row.eve_type_id: row for row in order.items.all()}
    for type_id, buy_qty in effective_buy.items():
        if buy_qty <= 0:
            continue
        row = items.get(type_id)
        if row is None or row.jita_sell_volume is None:
            continue
        if buy_qty > int(row.jita_sell_volume):
            count += 1
    return count


def multibuy_blocked(
    order: FittingBuyOrder, plan: ShoppingPlan | None = None
) -> tuple[bool, str]:
    """Whether Copy Multibuy should be blocked, with a short reason code."""
    shopping = _plan(order, plan)
    buy_types = sum(1 for qty in shopping.buy.values() if qty > 0)
    if buy_types > 100:
        return True, "too_large"
    if order.jita_checked_at is None and buy_types > 0:
        return True, "jita_pending"
    shorts = order_blocking_short_count(order, shopping)
    if shorts > 0:
        return True, "shorts"
    return False, ""


def shopping_landed_complete(
    order: FittingBuyOrder, plan: ShoppingPlan | None = None
) -> bool:
    """True when every type still to buy has a pasted unit_price."""
    shopping = _plan(order, plan)
    effective_buy = effective_buy_map(order, shopping)
    if not any(qty > 0 for qty in effective_buy.values()):
        return True
    items = {row.eve_type_id: row for row in order.items.all()}
    for type_id, buy_qty in effective_buy.items():
        if buy_qty <= 0:
            continue
        row = items.get(type_id)
        if row is None or row.unit_price is None:
            return False
    return True


def resolve_guide_step(
    order: FittingBuyOrder, plan: ShoppingPlan | None = None
) -> str:
    """Derive guided step (stock / purchase / contract) from order state."""
    if order.status in (
        FittingBuyOrderStatus.COMPLETED,
        FittingBuyOrderStatus.ARCHIVED,
    ):
        return FittingBuyGuideStep.CONTRACT
    if order.stock_paste is None:
        return FittingBuyGuideStep.STOCK
    if shopping_landed_complete(order, plan):
        return FittingBuyGuideStep.CONTRACT
    return FittingBuyGuideStep.PURCHASE
