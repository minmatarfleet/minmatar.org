"""Test helpers for industry models."""

from __future__ import annotations

from industry.helpers.public_short_code import (
    pick_unique_public_short_code_among_actives,
)
from industry.models import IndustryOrder


def create_industry_order(**kwargs) -> IndustryOrder:
    """Like ``IndustryOrder.objects.create`` but assigns ``public_short_code`` if omitted."""
    if "public_short_code" not in kwargs:
        kwargs["public_short_code"] = (
            pick_unique_public_short_code_among_actives()
        )
    return IndustryOrder.objects.create(**kwargs)


def set_stored_profit_breakdown(
    order: IndustryOrder, profit_per_unit_by_type: dict[int, int]
) -> IndustryOrder:
    """Store a minimal profit breakdown snapshot (rows + totals) on ``order``."""
    qty_by_type = {
        item.eve_type_id: item.quantity for item in order.items.all()
    }
    rows = [
        {
            "type_id": type_id,
            "qty": qty_by_type.get(type_id, 0),
            "profit_per": profit_per,
            "order_profit": profit_per * qty_by_type.get(type_id, 0),
        }
        for type_id, profit_per in profit_per_unit_by_type.items()
    ]
    order.profit_breakdown = {
        "rows": rows,
        "totals": {"total_profit": sum(r["order_profit"] for r in rows)},
    }
    order.save(update_fields=["profit_breakdown"])
    return order
