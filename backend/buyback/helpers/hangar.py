"""Tracked buyback hangar asset helpers."""

from __future__ import annotations

import logging
from collections import defaultdict

from eveonline.client import EsiClient
from eveonline.helpers.corporations import get_director_with_scope
from eveonline.models import EveCorporation

from buyback.models import (
    BUYBACK_CORPORATION_ID,
    EveBuybackSettings,
)

logger = logging.getLogger(__name__)

SCOPE_CORPORATION_ASSETS = ["esi-assets.read_corporation_assets.v1"]


def fetch_corporation_assets() -> list[dict]:
    """ESI corp assets for M-EXC, or [] if no director / ESI error."""
    try:
        corp = EveCorporation.objects.get(
            corporation_id=BUYBACK_CORPORATION_ID
        )
    except EveCorporation.DoesNotExist:
        logger.warning("M-EXC corporation %s missing", BUYBACK_CORPORATION_ID)
        return []

    character = get_director_with_scope(corp, SCOPE_CORPORATION_ASSETS)
    if character is None:
        logger.warning(
            "No director with corp assets scope for %s", BUYBACK_CORPORATION_ID
        )
        return []

    response = EsiClient(character).get_corporation_assets(
        BUYBACK_CORPORATION_ID
    )
    if not response.success():
        logger.warning(
            "Corp assets ESI failed for %s: %s",
            BUYBACK_CORPORATION_ID,
            response.response_code,
        )
        return []
    return list(response.results() or [])


def stockpile_config(
    settings: EveBuybackSettings | None = None,
) -> dict:
    buyback = settings or EveBuybackSettings.load()
    return {
        "structure_id": int(buyback.stockpile_structure_id),
        "office_id": int(buyback.stockpile_office_id),
        "hangar_flag": buyback.stockpile_hangar_flag,
        "include_deliveries": bool(buyback.stockpile_include_deliveries),
    }


def asset_in_tracked_stockpile(asset: dict, config: dict) -> bool:
    location_id = asset.get("location_id")
    flag = asset.get("location_flag")
    if location_id is None or flag is None:
        return False
    if (
        config["include_deliveries"]
        and location_id == config["structure_id"]
        and flag == "CorpDeliveries"
    ):
        return True
    if location_id == config["office_id"] and flag == config["hangar_flag"]:
        return True
    return False


def quantities_from_assets(
    assets: list[dict],
    *,
    settings: EveBuybackSettings | None = None,
) -> dict[int, int]:
    """type_id → qty in tracked Deliveries + Director hangar."""
    config = stockpile_config(settings)
    totals: dict[int, int] = defaultdict(int)
    for asset in assets:
        if not asset_in_tracked_stockpile(asset, config):
            continue
        type_id = asset.get("type_id")
        if type_id is None:
            continue
        qty = int(asset.get("quantity") or 0)
        if qty <= 0:
            continue
        totals[int(type_id)] += qty
    return dict(totals)


def fetch_stockpile_quantities(
    *, settings: EveBuybackSettings | None = None
) -> dict[int, int]:
    return quantities_from_assets(
        fetch_corporation_assets(), settings=settings
    )
