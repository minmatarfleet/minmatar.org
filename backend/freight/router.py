from typing import List

from ninja import Router
from pydantic import BaseModel

from .models import EveFreightRoute

# Create your views here.
router = Router(tags=["Freight"])


class EveFreightLocationResponse(BaseModel):
    location_id: int
    name: str
    short_name: str


class EveFreightRouteResponse(BaseModel):
    orgin: EveFreightLocationResponse
    destination: EveFreightLocationResponse
    bidirectional: bool


class EveFreightRouteOptionResponse(BaseModel):
    route_id: int
    maximum_m3: int


class EveFreightRouteCostResponse(BaseModel):
    route_id: int
    cost: int


class EveFreightRouteCostRequest(BaseModel):
    m3: int
    collateral: int


@router.get("/routes", response=List[EveFreightRouteResponse])
def get_routes(request):
    routes = EveFreightRoute.objects.all()
    response = []
    for route in routes:
        response.append(
            EveFreightRouteResponse(
                orgin=EveFreightLocationResponse(
                    location_id=route.orgin.location_id,
                    name=route.orgin.name,
                    short_name=route.orgin.short_name,
                ),
                destination=EveFreightLocationResponse(
                    location_id=route.destination.location_id,
                    name=route.destination.name,
                    short_name=route.destination.short_name,
                ),
                bidirectional=route.bidirectional,
            )
        )
    return response


@router.get("{route_id}/options", response=List[EveFreightRouteOptionResponse])
def get_route_options(request, route_id: int):
    route = EveFreightRoute.objects.get(id=route_id)
    options = route.evefreightrouteoption_set.all()
    response = []
    for option in options:
        response.append(
            EveFreightRouteOptionResponse(
                route_id=route_id,
                maximum_m3=option.maximum_m3,
            )
        )
    return response


@router.get("/routes/{route_id}/cost", response=EveFreightRouteCostResponse)
def get_route_cost(request, route_id: int, m3: int, collateral: int):
    route = EveFreightRoute.objects.get(id=route_id)
    cost = route.base_cost + (route.collateral_modifier * collateral)
    return EveFreightRouteCostResponse(route_id=route_id, cost=cost)
