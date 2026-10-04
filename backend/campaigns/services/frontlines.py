"""Advantage from CCP's frontlines page, so pilots do not have to report it.

ESI exposes no advantage, but https://www.eveonline.com/frontlines does: its
map is fed by ``/api/warzone/status``, one public JSON document for the whole
warzone with each faction's advantage per system. The page caches it for a
few minutes, which is as fresh as any pilot's reading and far more reliable.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import requests
from django.utils import timezone

from campaigns.models import (
    Campaign,
    CampaignAdvantageReading,
    CampaignSystem,
)
from campaigns.services import advantage

logger = logging.getLogger(__name__)

WARZONE_STATUS_URL = "https://www.eveonline.com/api/warzone/status"
USER_AGENT = "minmatar.org campaigns (https://my.minmatar.org)"
MINMATAR_FACTION_ID = 500002
AMARR_FACTION_ID = 500003
# The page itself is served with max-age 150s; re-recording an unchanged
# reading more often than this only pads the table.
MIN_INTERVAL_MINUTES = 10


def _as_system_id(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_warzone_status() -> list[dict]:
    """The whole warzone, or an empty list when the page is unreachable."""
    try:
        response = requests.get(
            WARZONE_STATUS_URL,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        logger.warning("Frontlines status fetch failed: %s", error)
        return []
    return payload if isinstance(payload, list) else []


def advantage_for(entry: dict, faction_id: int) -> float | None:
    """One faction's total advantage in a status entry, 0-100."""
    for row in entry.get("advantage") or []:
        if row.get("factionID") == faction_id:
            try:
                return max(0.0, min(100.0, float(row.get("totalAmount", 0))))
            except (TypeError, ValueError):
                return None
    return None


def record_advantage(
    status: list[dict] | None = None,
    *,
    campaign: Campaign | None = None,
    force: bool = False,
) -> dict:
    """Write one frontlines reading per live campaign system.

    A reading is only written when the numbers moved or the last one is
    older than ``MIN_INTERVAL_MINUTES``, so the state stays fresh without
    the table filling with identical rows. ``force`` is the operator
    refresh: every theater system gets a current reading.
    """
    status = fetch_warzone_status() if status is None else status
    if not status:
        return {"systems": 0, "written": 0}

    by_id = {}
    for entry in status:
        system_id = _as_system_id(entry.get("solarsystemID"))
        if system_id is not None:
            by_id[system_id] = entry
    campaign_systems = CampaignSystem.objects.filter(
        retired_at__isnull=True,
        campaign__status__in=["scheduled", "active"],
    )
    if campaign is not None:
        campaign_systems = campaign_systems.filter(campaign=campaign)
    written = 0
    seen = 0
    since = timezone.now() - timedelta(minutes=MIN_INTERVAL_MINUTES)

    for campaign_system in campaign_systems:
        system_id = _as_system_id(campaign_system.solar_system_id)
        entry = by_id.get(system_id) if system_id is not None else None
        if not entry:
            continue
        ours = advantage_for(entry, MINMATAR_FACTION_ID)
        theirs = advantage_for(entry, AMARR_FACTION_ID)
        if ours is None or theirs is None:
            continue
        seen += 1

        recent = (
            CampaignAdvantageReading.objects.filter(
                campaign_system=campaign_system,
                source="frontlines",
                reported_at__gte=since,
            )
            .order_by("-reported_at")
            .first()
        )
        if (
            not force
            and recent
            and recent.our_pct == ours
            and recent.enemy_pct == theirs
        ):
            continue

        CampaignAdvantageReading.objects.create(
            campaign_system=campaign_system,
            reported_by=None,
            our_pct=ours,
            enemy_pct=theirs,
            source="frontlines",
            status="accepted",
        )
        advantage.recompute_state(campaign_system)
        written += 1

    return {"systems": seen, "written": written}
