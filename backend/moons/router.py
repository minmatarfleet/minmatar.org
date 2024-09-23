from typing import List

from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from moons.models import EveMoon, EveMoonDistribution

from .parser import process_moon_paste, MoonParsingResult

moons_router = Router(tags=["Moons"])
moons_paste_router = Router(tags=["Moons"])


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


class CreateMoonFromPasteRequest(BaseModel):
    paste: str


class MoonSummaryResponse(BaseModel):
    system: str
    scanned_moons: int


@moons_paste_router.post(
    "",
    response={
        200: MoonParsingResult,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def create_moon_from_paste(
    request, moon_paste_request: CreateMoonFromPasteRequest
) -> MoonParsingResult:
    if not request.user.has_perm("moons.add_evemoon"):
        return 403, ErrorResponse(
            detail="You do not have permission to add moons"
        )

    results = process_moon_paste(
        moon_paste_request.paste, user_id=request.user.id
    )
    return results


def count_scanned_moons(eve_moons) -> List[MoonSummaryResponse]:
    moon_counts = {}

    for moon in eve_moons:
        print(moon.system, moon.planet, moon.moon)
        if moon.system not in moon_counts:
            moon_counts[moon.system] = 0

        moon_counts[moon.system] += 1

    response = []

    for system, moons in moon_counts.items():
        response.append(
            MoonSummaryResponse(system=system, scanned_moons=moons)
        )

    return response


@moons_router.get(
    "/summary",
    response={
        200: List[MoonSummaryResponse],
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def get_moon_summary(request):
    if not request.user.has_perm("moons.view_evemoon"):
        return 403, ErrorResponse(
            detail="You do not have permission to view moons"
        )

    return count_scanned_moons(EveMoon.objects.all())


@moons_router.get(
    "",
    response={
        200: List[MoonViewResponse],
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def get_moons(request, system: str = None):
    if not request.user.has_perm("moons.view_evemoon"):
        return 403, ErrorResponse(
            detail="You do not have permission to view moons"
        )

    moons = EveMoon.objects.all()
    if system:
        moons = moons.filter(system=system)
    response = []
    for moon in moons:
        if moon.reported_by is None:
            reported_by_user = "{Unknown}"
        else:
            reported_by_user = moon.reported_by.username
        response.append(
            MoonViewResponse(
                id=moon.id,
                system=moon.system,
                planet=moon.planet,
                moon=moon.moon,
                reported_by=reported_by_user,
            )
        )
    return response


# @moons_router.get("/{moon_id}", response=MoonResponse)
def get_moon(request, moon_id: int):
    if not request.user.has_perm("moons.manage_evemoon"):
        return ErrorResponse(detail="You do not have permission to view moons")

    moon = EveMoon.objects.get(id=moon_id)
    distribution = EveMoonDistribution.objects.filter(moon=moon)

    if moon.reported_by is None:
        reported_by_user = "{Unknown}"
    else:
        reported_by_user = moon.reported_by.username

    response = MoonResponse(
        id=moon.id,
        system=moon.system,
        planet=moon.planet,
        moon=moon.moon,
        reported_by=reported_by_user,
        distribution=[
            MoonDistributionResponse(ore=d.ore, percentage=d.yield_percent)
            for d in distribution
        ],
    )
    return response


# @moons_router.post("", response=int)
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
