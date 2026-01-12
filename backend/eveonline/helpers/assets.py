import json
import logging
from typing import List, Optional

import pydantic

from eveonline.client import EsiClient
from eveonline.models import EveCharacter, EveCharacterAsset
from structures.models import EveStructure

logger = logging.getLogger(__name__)


class EveAssetResponse(pydantic.BaseModel):
    is_blueprint_copy: Optional[bool] = None
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


def non_ship_location(location_flag: str) -> bool:
    if "FighterTube" in location_flag:
        return True
    if "Slot" in location_flag:
        return True
    if "Hold" in location_flag:
        return True
    if "Bay" in location_flag:
        return True
    if location_flag in [
        "BoosterBay",
        "CorpseBay",
        "DroneBay",
        "FighterBay",
        "HiddenModifiers",
        "Implant",
        "InfrastructureHangar",
        "Locked",
        "Skill",
        "Unlocked",
        "Wardrobe",
    ]:
        return True

    return False


def create_character_assets(character: EveCharacter, assets_data: List[dict]):
    """Create assets for a character from ESI assets data"""
    updated = 0
    created = 0
    deleted = 0
    logger.debug("Creating assets for character %s", character.character_id)
    deleted, _ = EveCharacterAsset.objects.filter(character=character).delete()
    logger.debug("Loading assets for character %s", character.character_id)

    not_ship = "NOT A SHIP"

    # Cache of type ID to type names mappings
    type_names = {}

    esi = EsiClient(None)
    assets: List[EveAssetResponse] = [EveAssetResponse(**asset) for asset in assets_data]
    for asset in assets:
        logger.debug("Processing asset %s", asset)

        if non_ship_location(asset.location_flag):
            continue

        # Check location type first as it can rule out a lot of items quickly
        location = None
        if asset.location_type == "station":
            location = esi.get_station(asset.location_id)
        elif asset.location_type == "item":
            if EveStructure.objects.filter(id=asset.location_id).exists():
                location = EveStructure.objects.get(id=asset.location_id)
            else:
                continue
        else:
            continue

        if non_ship_location(asset.location_flag):
            continue

        if asset.is_blueprint_copy:
            type_names[asset.type_id] = not_ship
            continue

        if asset.type_id in type_names:
            # Already looked up this type
            type_name = type_names[asset.type_id]
            if type_name == not_ship:
                continue
        else:
            # Lookup and cache name for type_id
            eve_type = esi.get_eve_type(asset.type_id, True)
            if eve_type.eve_group is None:
                type_names[asset.type_id] = not_ship
                continue
            eve_group = esi.get_eve_group(eve_type.eve_group.id, True)
            eve_category = eve_group.eve_category
            if eve_category.name != "Ship":
                type_names[asset.type_id] = not_ship
                continue
            type_name = eve_type.name
            logger.debug("Found asset %s", type_name)
            type_names[asset.type_id] = type_name

        EveCharacterAsset.objects.create(
            type_id=eve_type.id,
            type_name=type_name,
            location_id=asset.location_id,
            location_name=location.name,
            character=character,
            item_id=asset.item_id,
        )
        created += 1

    return (created, updated, deleted)
