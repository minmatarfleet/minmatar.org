import logging

from ninja import Router
from pydantic import BaseModel
from typing import List

from django.contrib.auth.models import User

from authentication import AuthBearer

from groups.helpers import user_in_team, TECH_TEAM
from eveonline.models import EveCharacterAsset, EveCorporation

logger = logging.getLogger(__name__)

router = Router(tags=["Assets"])


class ErrorResponse(BaseModel):
    detail: str


class ShipAsset(BaseModel):
    location_name: str
    type_name: str
    total: int = 0


SHIP_ASSET_TYPE_ID_FILTER = [
    72811,  # Cyclone Fleet Issue
    17732,  # Tempest Fleet Issue
    29344,  # Exeq Navy
    72872,  # Proph Navy
    638,  # Raven
    33820,  # Bhargest
]


def permitted(user: User) -> bool:
    if user.is_superuser:
        return True
    if user_in_team(user, TECH_TEAM):
        return True
    return False


@router.get(
    "/ships",
    summary="Get a summary of alliance member ship assets",
    auth=AuthBearer(),
    response={200: List[ShipAsset], 403: ErrorResponse},
)
def get_(request, primary_character_id: int = None):
    if not permitted(request.user):
        return 403, ErrorResponse(detail="Not permitted")

    summary = {}

    fl33t_corp_ids = EveCorporation.objects.filter(
        alliance__ticker="FL33T"
    ).values_list("corporation_id", flat=True)
    assets = EveCharacterAsset.objects.filter(
        character__corporation_id__in=fl33t_corp_ids
    )
    for asset in assets:
        if asset.type_id not in SHIP_ASSET_TYPE_ID_FILTER:
            continue

        key = f"{asset.location_id}/{asset.type_id}"
        if key not in summary:
            summary[key] = ShipAsset(
                type_name=asset.type_name, location_name=asset.location_name
            )
        summary[key].total += 1

    return summary.values()
