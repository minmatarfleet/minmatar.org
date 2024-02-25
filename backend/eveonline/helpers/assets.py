import json
import logging
from typing import List, Optional

import pydantic
from esi.clients import EsiClientProvider
from esi.models import Token
from eveuniverse.models import EveStation, EveType

from eveonline.models import EveCharacter, EveCharacterAsset

logger = logging.getLogger(__name__)
esi = EsiClientProvider()


class EveAssetResponse(pydantic.BaseModel):
    is_blueprint_copy: Optional[bool]
    is_singleton: bool
    item_id: int
    location_flag: str
    location_id: int
    location_type: str
    quantity: int
    type_id: int


class EveStructureResponse(pydantic.BaseModel):
    name: str
    solar_system_id: int


def create_character_assets(character: EveCharacter):
    """Create assets for a character"""
    EveCharacterAsset.objects.filter(character=character).delete()
    required_scopes = [
        "esi-assets.read_assets.v1",
        "esi-universe.read_structures.v1",
    ]
    assets: List[EveAssetResponse] = json.loads(character.assets_json)
    for asset in assets:
        asset = EveAssetResponse(**asset)
        print(asset)
        eve_type, _ = EveType.objects.get_or_create_esi(id=asset.type_id)
        location = None
        if asset.location_type == "station":
            location, _ = EveStation.objects.get_or_create_esi(
                id=asset.location_id
            )
        elif asset.location_type == "other":
            # fetch structure
            token = Token.objects.filter(
                character_id=character.character_id,
                scopes__name__in=required_scopes,
            ).first()
            if token is None:
                logger.error(
                    "No token found for character %s",
                    character.character_id,
                )
                continue
            location: EveStructureResponse = (
                esi.client.Universe.get_universe_structures_structure_id(
                    structure_id=asset.location_id,
                    token=token.valid_access_token(),
                ).results()
            )
        else:
            logger.info("Unknown location type: %s", asset.location_type)
            continue

        EveCharacterAsset.objects.create(
            type_id=eve_type.id,
            type_name=eve_type.name,
            location_id=asset.location_id,
            location_name=location.name,
            character=character,
        )
    return True
