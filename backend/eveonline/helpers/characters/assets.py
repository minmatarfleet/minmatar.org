import logging
from typing import Dict, List, Optional

import pydantic

from eveonline.client import EsiClient
from eveonline.helpers.db_sync import replace_with_bulk_create
from eveonline.models import EveCharacter, EveCharacterAsset, EveLocation
from eveuniverse.models import EveStation, EveType

logger = logging.getLogger(__name__)

BULK_CREATE_BATCH = 500


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


def _ship_type_names_by_id(
    type_ids: set[int], esi: EsiClient
) -> Dict[int, Optional[str]]:
    """
    Return type_id -> ship type name, or None if the type is not a ship.
    Uses DB first; falls back to ESI once per missing type_id.
    """
    if not type_ids:
        return {}

    not_ship = object()
    resolved: Dict[int, object] = {}
    types_by_id = {
        eve_type.id: eve_type
        for eve_type in EveType.objects.filter(id__in=type_ids).select_related(
            "eve_group__eve_category"
        )
    }

    for type_id in type_ids:
        eve_type = types_by_id.get(type_id)
        if eve_type is None:
            eve_type = esi.get_eve_type(type_id, True)
            types_by_id[type_id] = eve_type

        if eve_type.eve_group is None:
            resolved[type_id] = not_ship
            continue
        category = eve_type.eve_group.eve_category
        category_name = (
            category.name
            if category and isinstance(category.name, str)
            else None
        )
        if not category_name:
            eve_group = esi.get_eve_group(eve_type.eve_group.id, True)
            category_name = eve_group.eve_category.name
        if category_name != "Ship":
            resolved[type_id] = not_ship
        else:
            resolved[type_id] = eve_type.name

    return {
        type_id: (name if name is not not_ship else None)
        for type_id, name in resolved.items()
    }


def _station_names_by_id(
    station_ids: set[int], esi: EsiClient
) -> Dict[int, str]:
    if not station_ids:
        return {}

    names = {
        station.id: station.name
        for station in EveStation.objects.filter(id__in=station_ids)
    }
    for station_id in station_ids - set(names):
        names[station_id] = esi.get_station(station_id).name
    return names


def _item_location_names_by_id(location_ids: set[int]) -> Dict[int, str]:
    if not location_ids:
        return {}

    names = {
        location.location_id: location.location_name
        for location in EveLocation.objects.filter(
            location_id__in=location_ids
        )
    }
    for location_id in location_ids - set(names):
        names[location_id] = "Unknown Location - " + str(location_id)
    return names


def create_character_assets(character: EveCharacter, assets_data: List[dict]):
    """Create assets for a character from ESI assets data"""
    logger.debug("Creating assets for character %s", character.character_id)
    esi = EsiClient(None)
    assets: List[EveAssetResponse] = [
        EveAssetResponse(**asset) for asset in assets_data
    ]

    candidate_assets = [
        asset
        for asset in assets
        if not non_ship_location(asset.location_flag)
        and asset.location_type in ("station", "item")
        and not asset.is_blueprint_copy
    ]

    type_ids = {asset.type_id for asset in candidate_assets}
    station_ids = {
        asset.location_id
        for asset in candidate_assets
        if asset.location_type == "station"
    }
    item_location_ids = {
        asset.location_id
        for asset in candidate_assets
        if asset.location_type == "item"
    }

    ship_names_by_type_id = _ship_type_names_by_id(type_ids, esi)
    station_names = _station_names_by_id(station_ids, esi)
    item_location_names = _item_location_names_by_id(item_location_ids)

    instances = []
    for asset in candidate_assets:
        type_name = ship_names_by_type_id.get(asset.type_id)
        if not type_name:
            continue

        if asset.location_type == "station":
            location_name = station_names[asset.location_id]
        else:
            location_name = item_location_names[asset.location_id]

        instances.append(
            EveCharacterAsset(
                type_id=asset.type_id,
                type_name=type_name,
                location_id=asset.location_id,
                location_name=location_name,
                character=character,
                item_id=asset.item_id,
            )
        )

    deleted_queryset = EveCharacterAsset.objects.filter(character=character)
    deleted_count = deleted_queryset.count()
    created = replace_with_bulk_create(
        delete_queryset=deleted_queryset,
        instances=instances,
    )
    return (created, 0, deleted_count)
