"""Schemas for order breakdown endpoints (nested material trees)."""

from typing import List

from pydantic import BaseModel


class NestedBreakdownNode(BaseModel):
    """One node in a nested material breakdown tree."""

    name: str
    type_id: int
    quantity: int
    source: str
    depth: int
    children: List["NestedBreakdownNode"] = []


NestedBreakdownNode.model_rebuild()


class OrderBreakdownResponse(BaseModel):
    """Nested breakdown for an order: one root per product type in the order."""

    roots: List[NestedBreakdownNode]
