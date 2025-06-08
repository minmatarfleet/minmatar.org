import json
import logging
from typing import List, Optional

import pydantic
from esi.clients import EsiClientProvider

from eveonline.client import EsiClient
from eveonline.models import EveCharacter, EveCharacterAsset
from structures.models import EveStructure

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
    logger.info("Creating assets for character %s", character.character_id)
    EveCharacterAsset.objects.filter(character=character).delete()
    logger.debug("Loading assets for character %s", character.character_id)
    assets: List[EveAssetResponse] = json.loads(character.assets_json)
    for asset in assets:
        logger.debug("Processing asset %s", asset)
        asset = EveAssetResponse(**asset)
        esi_client = EsiClient(None)
        eve_type = esi_client.get_eve_type(asset.type_id, True)
        if eve_type.eve_group is None:
            continue
        eve_group = esi_client.get_eve_group(eve_type.eve_group.id, True)
        eve_category = eve_group.eve_category
        if eve_category.name != "Ship":
            continue
        logger.debug("Found asset %s", eve_type.name)
        location = None
        if asset.location_type == "station":
            location = esi_client.get_station(asset.location_id)
        elif asset.location_type == "item":
            if EveStructure.objects.filter(id=asset.location_id).exists():
                location = EveStructure.objects.get(id=asset.location_id)
            else:
                continue
        else:
            continue

        EveCharacterAsset.objects.create(
            type_id=eve_type.id,
            type_name=eve_type.name,
            location_id=asset.location_id,
            location_name=location.name,
            character=character,
        )
    return True
