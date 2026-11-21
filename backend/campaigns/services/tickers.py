"""Alliance tickers for campaign rows, from what the site already stores.

Never calls ESI: the local alliance table first, then the tickers operators
typed on the campaign's parties. A row with neither shows the alliance name.
"""

from __future__ import annotations

from collections.abc import Iterable

from campaigns.models import Campaign, CampaignParty
from eveonline.models import EveAlliance


def alliance_tickers(
    alliance_ids: Iterable[int | None], campaign: Campaign | None = None
) -> dict[int, str]:
    ids = {int(alliance_id) for alliance_id in alliance_ids if alliance_id}
    if not ids:
        return {}
    tickers: dict[int, str] = {}
    if campaign is not None:
        for alliance_id, ticker in CampaignParty.objects.filter(
            campaign=campaign, alliance_id__in=ids
        ).values_list("alliance_id", "ticker"):
            if ticker:
                tickers[alliance_id] = ticker
    for alliance_id, ticker in EveAlliance.objects.filter(
        alliance_id__in=ids
    ).values_list("alliance_id", "ticker"):
        if ticker:
            tickers[alliance_id] = ticker
    return tickers


def owner_alliance(structure) -> tuple[int | None, str]:
    """The alliance a structure answers to: the affiliated alliance when the
    legal owner is an alt corporation, else the owner's own."""
    if structure.related_alliance_id:
        return (
            structure.related_alliance_id,
            structure.related_alliance_name or structure.alliance_name or "",
        )
    return structure.alliance_id, structure.alliance_name or ""
