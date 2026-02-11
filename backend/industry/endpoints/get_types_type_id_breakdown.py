from typing import List

from eveuniverse.models import EveType
from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from industry.helpers.type_breakdown import get_nested_breakdown

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
)
def get_types_type_id_breakdown(request, type_id: int, quantity: int = 1):
    """Return nested component breakdown for an Eve type (e.g. ship, module)."""
    try:
        eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
    except Exception:
        return 404, ErrorResponse(detail=f"Type {type_id} not found")
    data = get_nested_breakdown(eve_type, quantity=quantity)
    return 200, NestedBreakdownNode(**data)
