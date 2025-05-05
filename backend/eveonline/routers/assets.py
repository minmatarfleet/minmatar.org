import logging

from ninja import Router
from pydantic import BaseModel
from typing import List

from authentication import AuthBearer

from eveonline.models import EveCharacterAsset

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


@router.get(
    "/ships",
    summary="Get a summary of alliance member ship assets",
    auth=AuthBearer(),
    response={200: List[ShipAsset], 404: ErrorResponse},
)
def get_(request, primary_character_id: int = None):
    summary = {}

    assets = EveCharacterAsset.objects.filter(
        character__corporation__alliance__ticker="FL33T"
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
