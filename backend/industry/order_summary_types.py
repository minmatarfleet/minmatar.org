"""Typed rows for industry order Discord summary assembly."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ActiveOrderSummaryLine:
    public_short_code: str
    location_label: str
    group_names_csv: str
    profit_isk: Decimal


@dataclass(frozen=True)
class UnassignedOrderItemLine:
    public_short_code: str
    location_label: str
    eve_type_name: str
    unassigned_quantity: int
    profit_isk: Decimal


@dataclass(frozen=True)
class SummaryTotals:
    total_order_amount_isk: Decimal
    total_available_margin_isk: Decimal
