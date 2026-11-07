"""GET /invention/{type_id} - how a T2/T3 product's blueprint copy is invented."""

from eveuniverse.models import EveType

from app.errors import ErrorResponse
from industry.endpoints.planner.schemas import PlannerInventionInfoSchema
from industry.helpers.invention_planner import invention_outcomes, tech_kind
from industry.models import InventionDecryptor

PATH = "invention/{int:type_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": (
        "Invention sources (T1 blueprint or relic grades) and decryptors "
        "for a T2/T3 product; 404 when the product isn't invented"
    ),
    "response": {
        200: PlannerInventionInfoSchema,
        404: ErrorResponse,
    },
}


def get_invention(request, type_id: int):
    outcomes = invention_outcomes(type_id)
    if not outcomes:
        return 404, ErrorResponse(detail=f"Type {type_id} is not invented")
    name = (
        EveType.objects.filter(id=type_id)
        .values_list("name", flat=True)
        .first()
    )
    return 200, {
        "type_id": type_id,
        "name": name or str(type_id),
        "kind": tech_kind(outcomes),
        "sources": [
            {
                "type_id": o.source_type_id,
                "name": o.source_name,
                "kind": o.source_kind,
                "base_chance": o.probability,
                "runs": o.runs,
            }
            for o in outcomes
        ],
        "decryptors": [
            {
                "type_id": d.type_id,
                "name": d.name,
                "probability_multiplier": d.probability_multiplier,
                "runs_modifier": d.runs_modifier,
                "me_modifier": d.me_modifier,
                "te_modifier": d.te_modifier,
            }
            for d in InventionDecryptor.objects.all()
        ],
    }
