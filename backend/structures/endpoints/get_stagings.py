"""GET /locations/stagings - the home staging and the deployments."""

from typing import List

from django.core.cache import cache
from django.db.models import Q
from ninja import Router, Schema

from authentication import AuthOptional
from eveonline.models import EveLocation

from .. import locations as svc

router = Router(tags=["Structure browser"])

CACHE_KEY = "structures:stagings"
CACHE_SECONDS = 60


class StagingLocation(Schema):
    location_id: int
    name: str
    short_name: str
    solar_system_name: str


class Stagings(Schema):
    home: StagingLocation | None = None
    deployments: List[StagingLocation] = []


def _row(location_id, name, short_name, solar_system_name) -> dict:
    return {
        "location_id": location_id,
        "name": name,
        "short_name": short_name,
        "solar_system_name": solar_system_name,
    }


def _flagged() -> list:
    """Every flagged location, whoever may see it, kept briefly."""
    rows = cache.get(CACHE_KEY)
    if rows is None:
        rows = [
            {
                **_row(
                    loc.location_id,
                    loc.location_name,
                    loc.short_name,
                    loc.solar_system_name,
                ),
                "staging": loc.staging_active,
                "deployment": loc.deployment_active,
            }
            for loc in EveLocation.objects.filter(
                Q(staging_active=True) | Q(deployment_active=True)
            )
        ]
        cache.set(CACHE_KEY, rows, CACHE_SECONDS)
    return rows


@router.get(
    "/stagings",
    auth=AuthOptional(),
    response={200: Stagings},
    description=(
        "The home staging and the deployment locations this user may see."
    ),
)
def get_stagings(request):
    user = getattr(request, "user", None)
    flagged = _flagged()
    visible = set(
        svc.visible_locations(user)
        .filter(location_id__in=[row["location_id"] for row in flagged])
        .values_list("location_id", flat=True)
    )
    rows = sorted(
        (row for row in flagged if row["location_id"] in visible),
        key=lambda row: row["name"],
    )
    pick = ("location_id", "name", "short_name", "solar_system_name")
    home = next((row for row in rows if row["staging"]), None)
    return {
        "home": {key: home[key] for key in pick} if home else None,
        "deployments": [
            {key: row[key] for key in pick}
            for row in rows
            if row["deployment"] and not row["staging"]
        ],
    }
