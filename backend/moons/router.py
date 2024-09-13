from datetime import datetime
from typing import List

from ninja import Router
from pydantic import BaseModel

from .models import EveMoon, EveMoonDistribution
from app.errors import ErrorResponse

moons_router = Router(tags=["Moons"])


class MoonDistributionResponse(BaseModel):
    """Moon Distribution API Response"""

    ore: str
    percentage: float


class MoonViewResponse(BaseModel):
    id: int
    system: str
    planet: str
    moon: int
    reported_by: str


class MoonResponse(BaseModel):
    """Moons API Response"""

    id: int
    system: str
    planet: str
    moon: int
    reported_by: str
    distribution: List[MoonDistributionResponse]


class CreateMoonRequest(BaseModel):
    system: str
    planet: str
    moon: int
    distribution: List[MoonDistributionResponse]


@moons_router.get("", response=List[MoonViewResponse])
def get_moons(request, system: str = None):
    moons = EveMoon.objects.all()
    if system:
        moons = moons.filter(system=system)
    response = []
    for moon in moons:
        response.append(
            MoonViewResponse(
                id=moon.id,
                system=moon.system,
                planet=moon.planet,
                moon=moon.moon,
                reported_by=moon.reported_by.username,
            )
        )
    return response


@moons_router.get("/{moon_id}", response=MoonResponse)
def get_moon(request, moon_id: int):
    if not request.user.has_perm("moons.view_evemoon"):
        return ErrorResponse(detail="You do not have permission to view moons")

    moon = EveMoon.objects.get(id=moon_id)
    distribution = EveMoonDistribution.objects.filter(moon=moon)
    response = MoonResponse(
        id=moon.id,
        system=moon.system,
        planet=moon.planet,
        moon=moon.moon,
        ores=moon.ores,
        reported_by=moon.reported_by.username,
        distribution=[
            MoonDistributionResponse(ore=d.ore, percentage=d.yield_percent)
            for d in distribution
        ],
    )
    return response


@moons_router.post("", response=int)
def create_moon(request, moon_request: CreateMoonRequest):
    if not request.user.has_perm("moons.add_evemoon"):
        return ErrorResponse(detail="You do not have permission to add moons")

    moon = EveMoon.objects.create(
        system=moon_request.system,
        planet=moon_request.planet,
        moon=moon_request.moon,
        reported_by=request.user,
    )
    for distribution in moon_request.distribution:
        EveMoonDistribution.objects.create(
            moon=moon,
            ore=distribution.ore,
            yield_percent=distribution.percentage,
        )

    return moon.id
