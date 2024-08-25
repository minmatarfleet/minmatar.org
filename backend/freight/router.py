from ninja import Router
from .models import EveFreightLocation, EveFreightRoute, EveFreightRoute
from pydantic import BaseModel
from typing import List, Optional

# Create your views here.
router = Router(tags=["Freight"])


class EveFreightLocationResponse(BaseModel):
    location_id: int
    name: str
    short_name: str


class EveFreightRouteResponse(BaseModel):
    orgin: EveFreightLocation
    destination: EveFreightLocation
    bidirectional: bool


class EveFreightRouteOptionResponse(BaseModel):
    route: EveFreightRoute
    maximum_m3: int


class EveFreightRouteCostResponse(BaseModel):
    route: EveFreightRoute
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
                orgin=route.orgin,
                destination=route.destination,
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
                route=option.route,
                maximum_m3=option.maximum_m3,
            )
        )
    return response


@router.get("/routes/{route_id}/cost", response=EveFreightRouteCostResponse)
def get_route_cost(request, route_id: int, m3: int, collateral: int):
    route = EveFreightRoute.objects.get(id=route_id)
    cost = route.base_cost + (route.collateral_modifier * collateral)
    return EveFreightRouteCostResponse(route=route, cost=cost)
