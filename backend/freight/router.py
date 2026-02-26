import math
from typing import List

from ninja import Router
from pydantic import BaseModel

from freight.endpoints import router as endpoints_router
from .models import EveFreightRoute

router = Router(tags=["Freight"])
router.add_router("", endpoints_router)


class EveFreightLocationResponse(BaseModel):
    location_id: int
    name: str
    short_name: str


class EveFreightRouteResponse(BaseModel):
    route_id: int
    orgin: EveFreightLocationResponse
    destination: EveFreightLocationResponse
    expiration_days: int
    days_to_complete: int
    collateral_modifier: float


class EveFreightRouteCostResponse(BaseModel):
    route_id: int
    cost: int


@router.get("/routes", response=List[EveFreightRouteResponse])
def get_routes(request):
    routes = EveFreightRoute.objects.filter(active=True)
    response = []
    for route in routes:
        response.append(
            EveFreightRouteResponse(
                route_id=route.id,
                orgin=EveFreightLocationResponse(
                    location_id=route.origin_location.location_id,
                    name=route.origin_location.location_name,
                    short_name=route.origin_location.short_name,
                ),
                destination=EveFreightLocationResponse(
                    location_id=route.destination_location.location_id,
                    name=route.destination_location.location_name,
                    short_name=route.destination_location.short_name,
                ),
                expiration_days=route.expiration_days,
                days_to_complete=route.days_to_complete,
                collateral_modifier=route.collateral_modifier,
            )
        )
    return response


@router.get(
    "/routes/{route_id}/cost",
    response={200: EveFreightRouteCostResponse, 404: dict},
)
def get_route_cost(request, route_id: int, m3: int, collateral: int = 0):
    """Cost = isk_per_m3 * m3 + ceil(collateral_modifier * collateral)."""
    route = EveFreightRoute.objects.filter(id=route_id, active=True).first()
    if not route:
        return 404, {"detail": "Route not found."}
    cost = (route.isk_per_m3 * m3) + math.ceil(
        route.collateral_modifier * collateral
    )
    return EveFreightRouteCostResponse(route_id=route.id, cost=cost)
