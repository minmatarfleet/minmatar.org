"""Shared request/response schemas for order endpoints."""

from datetime import date, datetime
from typing import List

from pydantic import BaseModel


class OrderLocationResponse(BaseModel):
    """Location where the order should be built/delivered."""

    location_id: int
    location_name: str


class OrderListItemResponse(BaseModel):
    """One order in the list with location."""

    id: int
    created_at: datetime
    needed_by: date
    fulfilled_at: datetime | None
    character_id: int
    character_name: str
    location: OrderLocationResponse | None


class AssignmentResponse(BaseModel):
    """A character committed to build part of an order item."""

    character_id: int
    character_name: str
    quantity: int


class OrderItemResponse(BaseModel):
    """One line item with its assignments."""

    id: int
    eve_type_id: int
    eve_type_name: str
    quantity: int
    assignments: List[AssignmentResponse]


class OrderDetailResponse(BaseModel):
    """Full order with items and who committed to each item."""

    id: int
    created_at: datetime
    needed_by: date
    fulfilled_at: datetime | None
    character_id: int
    character_name: str
    location: OrderLocationResponse | None
    items: List[OrderItemResponse]


# Request schemas for POST /orders
class OrderItemInput(BaseModel):
    """One line item: eve type and quantity."""

    eve_type_id: int
    quantity: int


class CreateOrderRequest(BaseModel):
    """Request body for creating an industry order."""

    needed_by: date
    character_id: int | None = None
    location_id: int | None = None
    items: List[OrderItemInput]


class CreateOrderResponse(BaseModel):
    """Response after creating an order."""

    order_id: int
