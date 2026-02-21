"""Schemas for order breakdown endpoints (nested material trees)."""

from typing import List, Optional

from pydantic import BaseModel


class NestedBreakdownNode(BaseModel):
    """
    One node in a nested material breakdown tree.
    industry_product_id is set when this type is an IndustryProduct, so the client
    can fetch this node's breakdown via GET /products/{industry_product_id}/breakdown.
    """

    name: str
    type_id: int
    quantity: int
    source: str
    depth: int
    children: List["NestedBreakdownNode"] = []
    industry_product_id: Optional[int] = None

    @classmethod
    def from_breakdown_dict(cls, data: dict) -> "NestedBreakdownNode":
        """Build a NestedBreakdownNode from an enriched nested breakdown dict."""
        return cls(
            name=data["name"],
            type_id=data["type_id"],
            quantity=data["quantity"],
            source=data["source"],
            depth=data["depth"],
            industry_product_id=data.get("industry_product_id"),
            children=[
                cls.from_breakdown_dict(c) for c in data.get("children", [])
            ],
        )


NestedBreakdownNode.model_rebuild()


class OrderBreakdownResponse(BaseModel):
    """Nested breakdown for an order: one root per product type in the order."""

    roots: List[NestedBreakdownNode]


class AssignmentBreakdownResponse(BaseModel):
    """Material breakdown for one assignment (character + quantity) on an order item."""

    character_id: int
    character_name: str
    quantity: int
    breakdown: NestedBreakdownNode


class OrderItemAssignmentsBreakdownResponse(BaseModel):
    """Breakdown per assignment for an order item."""

    assignments: List[AssignmentBreakdownResponse]
