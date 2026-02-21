"""Deprecated: use industry product breakdown or order item breakdown endpoints instead."""

from typing import List

from eveuniverse.models import EveType
from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from industry.helpers.type_breakdown import get_breakdown_for_industry_product

router = Router(tags=["Industry - Breakdown"])


class NestedBreakdownNode(BaseModel):
    name: str
    type_id: int
    quantity: int
    source: str
    depth: int
    children: List["NestedBreakdownNode"] = []


NestedBreakdownNode.model_rebuild()


@router.get(
    "/types/{type_id}/breakdown",
    response={200: NestedBreakdownNode, 404: ErrorResponse},
    deprecated=True,
)
def get_types_type_id_breakdown(request, type_id: int, quantity: int = 1):
    """Return nested component breakdown for an Eve type (e.g. ship, module). Deprecated."""
    try:
        eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
    except Exception:
        return 404, ErrorResponse(detail=f"Type {type_id} not found")
    tree = get_breakdown_for_industry_product(eve_type, quantity=quantity)

    def tree_to_node(data: dict) -> NestedBreakdownNode:
        return NestedBreakdownNode(
            name=data["name"],
            type_id=data["type_id"],
            quantity=data["quantity"],
            source=data["source"],
            depth=data["depth"],
            children=[tree_to_node(c) for c in data.get("children", [])],
        )

    return 200, tree_to_node(tree)
