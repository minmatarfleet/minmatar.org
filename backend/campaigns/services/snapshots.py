"""Contested percentage, victory points and operational state per system.

ESI's factional warfare systems feed carries contested state, occupier, owner,
victory points and the threshold. It carries no operational state and no
advantage, so operational state is derived from a warzone jump graph and
advantage is handled separately.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import requests
from django.utils import timezone

from feed.constants import ESI_FW_SYSTEMS_URL, FEED_FW_ESI_USER_AGENT
from feed.models import FeedEvent

from campaigns.models import (
    Campaign,
    CampaignEvent,
    CampaignSystem,
    CampaignSystemSnapshot,
)
from campaigns.services import esi_gate
from campaigns.services.jump_graph import classify_system

logger = logging.getLogger(__name__)

MINMATAR_FACTION_ID = 500002
AMARR_FACTION_ID = 500003

THRESHOLD_WARN_PERCENT = 80.0


def fetch_fw_systems() -> list[dict]:
    """One public call returns the whole warzone; ESI caches it 30 minutes.

    We keep the raw entries rather than the feed's derived percentage,
    because victory points and the threshold are what a weekly capture
    target is measured in and the feed discards them.
    """
    if not esi_gate.can_spend("factional-warfare"):
        logger.warning("Skipping FW systems poll, ESI budget low")
        return []

    try:
        response = requests.get(
            ESI_FW_SYSTEMS_URL,
            headers={"User-Agent": FEED_FW_ESI_USER_AGENT},
            timeout=60,
        )
        esi_gate.observe_headers(dict(response.headers))
        esi_gate.spend("factional-warfare")
        response.raise_for_status()
    except requests.RequestException as error:
        esi_gate.record_error()
        logger.warning("FW systems poll failed: %s", error)
        return []

    return response.json() or []


def operational_state_for(
    solar_system_id: int, owner_faction_id, owners: dict | None = None
) -> str:
    """Frontline, command operations or rearguard.

    CCP derives this from adjacency to enemy-held systems, so the classifier
    needs ownership for the whole warzone, not just our campaign systems.
    Without the SDE jump-graph fixture the state stays unknown, which lowers
    the confidence of complex-class inference rather than inventing a
    multiplier. Run ``manage.py export_warzone_jump_graph`` to install it.
    """
    return classify_system(solar_system_id, owner_faction_id, owners)


def record_snapshots() -> dict:
    """Write one durable snapshot per campaign system."""
    systems = fetch_fw_systems()
    if not systems:
        return {"systems": 0, "written": 0}

    by_id = {row.get("solar_system_id"): row for row in systems}
    # Ownership for the entire warzone, which is what decides whether a
    # system sits on the frontline.
    owners = {
        row.get("solar_system_id"): row.get("owner_faction_id")
        for row in systems
    }
    now = timezone.now()
    written = 0

    campaign_systems = CampaignSystem.objects.filter(
        retired_at__isnull=True,
        campaign__status__in=["scheduled", "active"],
    ).select_related("campaign")

    for campaign_system in campaign_systems:
        row = by_id.get(campaign_system.solar_system_id)
        if not row:
            continue

        victory_points = int(row.get("victory_points") or 0)
        threshold = int(row.get("victory_points_threshold") or 0)
        contested_percent = (
            (victory_points / threshold * 100.0) if threshold else 0.0
        )
        owner_faction_id = row.get("owner_faction_id")

        previous = (
            CampaignSystemSnapshot.objects.filter(
                campaign_system=campaign_system
            )
            .order_by("-captured_at")
            .first()
        )

        CampaignSystemSnapshot.objects.create(
            campaign_system=campaign_system,
            captured_at=now,
            victory_points=victory_points,
            victory_points_threshold=threshold,
            contested_percent=contested_percent,
            occupier_faction_id=row.get("occupier_faction_id"),
            owner_faction_id=owner_faction_id,
            contested_state=str(row.get("contested") or ""),
            operational_state=operational_state_for(
                campaign_system.solar_system_id, owner_faction_id, owners
            ),
        )
        written += 1

        _maybe_emit_events(campaign_system, previous, contested_percent, row)

    return {"systems": len(campaign_systems), "written": written}


def _maybe_emit_events(campaign_system, previous, contested_percent, row):
    """Threshold and flip events for the timeline and notifications."""
    if not previous:
        return

    owner_faction_id = row.get("owner_faction_id")
    if (
        previous.owner_faction_id
        and owner_faction_id != previous.owner_faction_id
    ):
        ours = owner_faction_id == MINMATAR_FACTION_ID
        CampaignEvent.objects.create(
            campaign=campaign_system.campaign,
            kind=CampaignEvent.Kind.SYSTEM_FLIPPED,
            occurred_at=timezone.now(),
            title=(
                f"{campaign_system.name} flipped "
                f"{'to us' if ours else 'to them'}"
            ),
            campaign_system=campaign_system,
            side="friendly" if ours else "hostile",
            payload={"owner_faction_id": owner_faction_id},
        )
        return

    crossed = (
        previous.contested_percent
        < THRESHOLD_WARN_PERCENT
        <= contested_percent
    )
    if crossed:
        CampaignEvent.objects.create(
            campaign=campaign_system.campaign,
            kind=CampaignEvent.Kind.SYSTEM_THRESHOLD,
            occurred_at=timezone.now(),
            title=f"{campaign_system.name} is near the threshold",
            campaign_system=campaign_system,
            side="neutral",
            payload={"contested_percent": contested_percent},
        )


def system_trend(campaign_system, days: int = 7) -> list[dict]:
    """Daily contested readings for a system card's sparkline."""
    since = timezone.now() - timedelta(days=days)
    rows = (
        CampaignSystemSnapshot.objects.filter(
            campaign_system=campaign_system, captured_at__gte=since
        )
        .order_by("captured_at")
        .values("captured_at", "contested_percent", "victory_points")
    )
    return [
        {
            "captured_at": row["captured_at"].isoformat(),
            "contested_percent": round(row["contested_percent"], 2),
            "victory_points": row["victory_points"],
        }
        for row in rows
    ]


def mirror_feed_events(campaign: Campaign, hours: int = 48) -> int:
    """Copy the activity feed's events into the campaign timeline.

    A live Amarr fleet-activity event is the strongest reason to undock, so it
    also drives the hostile-gang signal on the Right now strip. These are
    detections, never scoring input.
    """
    system_ids = campaign.system_ids()
    if not system_ids:
        return 0

    since = timezone.now() - timedelta(hours=hours)
    mirrored = 0
    events = FeedEvent.objects.filter(occurred_at__gte=since).exclude(
        campaign_event__isnull=False
    )
    for event in events:
        payload = event.payload or {}
        # The feed writes the system as ``system_id``; accept both spellings.
        event_system = payload.get("system_id") or payload.get(
            "solar_system_id"
        )
        if event_system not in system_ids:
            continue

        campaign_system = CampaignSystem.objects.filter(
            campaign=campaign,
            solar_system_id=event_system,
            retired_at__isnull=True,
        ).first()

        kind = {
            "fleet_active": CampaignEvent.Kind.FLEET_ACTIVE,
            "killmail_batch": CampaignEvent.Kind.KILLMAIL_BATCH,
            "contested_change": CampaignEvent.Kind.CONTESTED_CHANGE,
        }.get(event.kind, CampaignEvent.Kind.KILLMAIL_BATCH)

        # The feed's accent already says whose event this is: amarr is
        # theirs, militia is ours, combat is nobody's in particular.
        side = {
            "amarr": "hostile",
            "militia": "friendly",
        }.get(event.accent, "neutral")
        if event.kind == "fleet_active" and side == "hostile":
            kind = CampaignEvent.Kind.HOSTILE_GANG

        CampaignEvent.objects.update_or_create(
            feed_event=event,
            defaults={
                "campaign": campaign,
                "kind": kind,
                "occurred_at": event.occurred_at,
                "ended_at": event.expires_at,
                "title": event.title,
                "body": event.preview or "",
                "payload": payload,
                "campaign_system": campaign_system,
                "side": side,
                "source": "feed",
                "is_active": event.is_active,
            },
        )
        mirrored += 1

    return mirrored
