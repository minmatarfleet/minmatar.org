"""Shared request/response schemas for order endpoints."""

from datetime import date, datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel


class OrderLocationResponse(BaseModel):
    """Location where the order should be built/delivered."""

    location_id: int
    location_name: str


class OrderItemQuantityResponse(BaseModel):
    """One item in an order with quantity (flat list entry)."""

    eve_type_id: int
    eve_type_name: str
    quantity: int
    target_unit_price: Decimal | None = None
    target_estimated_margin: Decimal | None = None


class OrderAssigneeResponse(BaseModel):
    """A character assigned to build something on this order (flat list entry)."""

    character_id: int
    character_name: str


class OrderListItemResponse(BaseModel):
    """One order in the list with location, flat items and assignees."""

    id: int
    created_at: datetime
    needed_by: date
    fulfilled_at: datetime | None
    public_short_code: str
    contract_to: str
    character_id: int
    character_name: str
    location: OrderLocationResponse | None
    items: List[OrderItemQuantityResponse]
    assigned_to: List[OrderAssigneeResponse]


class AssignmentResponse(BaseModel):
    """A character committed to build part of an order item."""

    id: int
    character_id: int
    character_name: str
    quantity: int
    target_unit_price: Decimal | None = None
    target_estimated_margin: Decimal | None = None
    delivered_at: datetime | None = None


class OrderItemResponse(BaseModel):
    """One line item with its assignments."""

    id: int
    eve_type_id: int
    eve_type_name: str
    quantity: int
    unassigned_quantity: int
    self_assign_maximum: int | None = None
    self_assign_window_ends_at: datetime
    target_unit_price: Decimal | None = None
    target_estimated_margin: Decimal | None = None
    assignments: List[AssignmentResponse]


class OrderDetailResponse(BaseModel):
    """Full order with items and who committed to each item."""

    id: int
    created_at: datetime
    needed_by: date
    fulfilled_at: datetime | None
    public_short_code: str
    contract_to: str
    character_id: int
    character_name: str
    location: OrderLocationResponse | None
    items: List[OrderItemResponse]


# Request schemas for POST /orders
class OrderItemInput(BaseModel):
    """One line item: eve type and quantity."""

    eve_type_id: int
    quantity: int
    self_assign_maximum: int | None = None


class CreateOrderRequest(BaseModel):
    """Request body for creating an industry order."""

    needed_by: date
    character_id: int | None = None
    location_id: int | None = None
    contract_to: str = ""
    items: List[OrderItemInput]


class CreateOrderResponse(BaseModel):
    """Response after creating an order."""

    order_id: int
    public_short_code: str


class PostOrderItemAssignmentRequest(BaseModel):
    """Assign quantity of a line to one of the user's characters."""

    character_id: int
    quantity: int


class PatchOrderItemAssignmentRequest(BaseModel):
    """Mark assignment delivery state."""

    delivered: bool


class ProfitSummaryOrderResponse(BaseModel):
    """One order candidate for the profit-summary filter UI."""

    id: int
    public_short_code: str
    needed_by: date
    location_label: str
    fulfilled_at: date | None
    item_count: int
    item_type_ids: List[int]
    included: bool


class ProfitSummaryRowResponse(BaseModel):
    """Aggregated product line with Amamake cost vs order ask (or Jita fallback)."""

    name: str
    type_id: int
    kind: str
    qty: int
    isk_per_lp: float | None
    cost_per: int
    unit_price: int
    price_source: str
    profit_per: int
    order_profit: int
    note: str | None = None


class ProfitSummaryTotalsResponse(BaseModel):
    total_order_amount: int
    total_profit: int
    line_count: int
    total_qty: int
    best_name: str | None
    best_profit: int | None
    worst_name: str | None
    worst_profit: int | None


class OrdersProfitSummaryResponse(BaseModel):
    """Canvas-style profit rollup for filtered industry orders."""

    orders: List[ProfitSummaryOrderResponse]
    rows: List[ProfitSummaryRowResponse]
    totals: ProfitSummaryTotalsResponse
    assumptions: List[str]
    facility_key: str
    compressed: bool
