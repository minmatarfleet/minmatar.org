"""Attach structures to campaigns: recon, timers, and killmail matches.

Attaching a structure adds its system to the campaign theater and to the
feed's monitored list so ship and capital kills on that grid start counting.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from eveuniverse.models import EveSolarSystem

from campaigns.constants import STRUCTURE_TYPE_BY_ID, STRUCTURE_TYPE_IDS
from campaigns.models import (
    Campaign,
    CampaignParty,
    CampaignStructure,
    CampaignSystem,
    PartyKind,
    PartySide,
    StructureAffiliation,
    StructureSource,
    StructureStatus,
    SystemGoal,
    SystemRole,
)
from eveonline.models import EveAlliance, EveCorporation
from feed.models import FeedMonitoredSystem

logger = logging.getLogger(__name__)


def resolve_system_id(system_name: str) -> tuple[int | None, str]:
    """Resolve a pasted system name to an id. Returns (id, canonical name)."""
    name = (system_name or "").strip()
    if not name:
        return None, ""

    # Prefer systems we already monitor; then the local SDE cache.
    monitored = FeedMonitoredSystem.objects.filter(name__iexact=name).first()
    if monitored:
        return int(monitored.solar_system_id), monitored.name

    system = EveSolarSystem.objects.filter(name__iexact=name).first()
    if system is not None:
        return int(system.id), system.name or name

    logger.warning("Could not resolve solar system %r", name)
    return None, name


def resolve_alliance_id(alliance_name: str | None) -> int | None:
    """Resolve a timer alliance name to an id when we already know them."""
    name = (alliance_name or "").strip()
    if not name:
        return None
    alliance = EveAlliance.objects.filter(name__iexact=name).first()
    return alliance.alliance_id if alliance else None


def resolve_corporation(
    corporation_name: str | None = None,
    corporation_id: int | None = None,
) -> tuple[int | None, str, int | None, str]:
    """Resolve owner corp to id/name and its alliance when known locally.

    Returns (corporation_id, corporation_name, alliance_id, alliance_name).
    """
    corp = None
    if corporation_id is not None:
        corp = (
            EveCorporation.objects.filter(corporation_id=corporation_id)
            .select_related("alliance")
            .first()
        )
    elif corporation_name and corporation_name.strip():
        corp = (
            EveCorporation.objects.filter(
                name__iexact=corporation_name.strip()
            )
            .select_related("alliance")
            .first()
        )

    if corp is None:
        return (
            corporation_id,
            (corporation_name or "").strip(),
            None,
            "",
        )

    alliance = corp.alliance
    return (
        int(corp.corporation_id),
        corp.name or (corporation_name or "").strip(),
        int(alliance.alliance_id) if alliance else None,
        alliance.name if alliance else "",
    )


def ensure_campaign_system(
    campaign: Campaign,
    solar_system_id: int,
    system_name: str,
) -> CampaignSystem:
    """Add the system to the campaign theater if it is not already there."""
    eve_system = EveSolarSystem.objects.filter(id=solar_system_id).first()
    defaults = {
        "name": system_name,
        "role": SystemRole.SUPPORT,
        "goal": SystemGoal.NONE,
        "is_fw_objective": False,
        "eve_solar_system": eve_system,
    }
    system, created = CampaignSystem.objects.get_or_create(
        campaign=campaign,
        solar_system_id=solar_system_id,
        defaults=defaults,
    )
    if created:
        logger.info(
            "Added system %s to campaign %s via structure attach",
            system_name,
            campaign.slug,
        )
    elif system.retired_at is not None:
        update_fields = ["retired_at", "name"]
        system.retired_at = None
        system.name = system_name or system.name
        if eve_system and not system.eve_solar_system_id:
            system.eve_solar_system = eve_system
            update_fields.append("eve_solar_system")
        system.save(update_fields=update_fields)
    return system


def ensure_feed_monitoring(
    solar_system_id: int, system_name: str
) -> FeedMonitoredSystem:
    """Make sure the zKill stream keeps mails for this system."""
    monitored, created = FeedMonitoredSystem.objects.get_or_create(
        solar_system_id=solar_system_id,
        defaults={
            "name": system_name,
            "source": FeedMonitoredSystem.Source.CAMPAIGN,
            "is_active": True,
        },
    )
    if not created and not monitored.is_active:
        monitored.is_active = True
        # Promote leftover manual rows so we know why they are watched.
        if monitored.source != FeedMonitoredSystem.Source.FW_WARZONE:
            monitored.source = FeedMonitoredSystem.Source.CAMPAIGN
            monitored.save(update_fields=["is_active", "source"])
        else:
            monitored.save(update_fields=["is_active"])
    elif created:
        logger.info(
            "Added %s to feed monitoring for a campaign theater", system_name
        )
    return monitored


def structure_type_for_ship_type(ship_type_id: int | None) -> str | None:
    """Map an ESI ship_type_id on a killmail to a structure type slug."""
    if not ship_type_id:
        return None
    return STRUCTURE_TYPE_BY_ID.get(int(ship_type_id))


def is_structure_type(ship_type_id: int | None) -> bool:
    return structure_type_for_ship_type(ship_type_id) is not None


def _normalize_reinforce_hour(reinforce_hour: int | None) -> int | None:
    if reinforce_hour is None:
        return None
    if (
        not isinstance(reinforce_hour, int)
        or reinforce_hour < 0
        or reinforce_hour > 23
    ):
        raise ValueError("reinforce_hour must be an integer between 0 and 23")
    return reinforce_hour


def _resolve_attach_system(
    solar_system_id: int | None, system_name: str
) -> tuple[int, str]:
    if solar_system_id is None:
        solar_system_id, system_name = resolve_system_id(system_name)
    elif not system_name:
        monitored = FeedMonitoredSystem.objects.filter(
            solar_system_id=solar_system_id
        ).first()
        system_name = monitored.name if monitored else str(solar_system_id)

    if solar_system_id is None:
        raise ValueError(f"unknown solar system: {system_name!r}")
    return solar_system_id, system_name


def _resolve_attach_ownership(
    *,
    corporation_name: str,
    corporation_id: int | None,
    alliance_name: str,
    alliance_id: int | None,
    related_alliance_name: str,
    related_alliance_id: int | None,
) -> tuple[int | None, str, int | None, str, int | None, str]:
    (
        resolved_corp_id,
        resolved_corp_name,
        corp_alliance_id,
        corp_alliance_name,
    ) = resolve_corporation(corporation_name, corporation_id)
    corporation_id = resolved_corp_id
    corporation_name = resolved_corp_name or corporation_name or ""

    if alliance_id is None and alliance_name:
        alliance_id = resolve_alliance_id(alliance_name)
    if alliance_id is None and corp_alliance_id is not None:
        alliance_id = corp_alliance_id
    if not alliance_name and corp_alliance_name:
        alliance_name = corp_alliance_name

    if related_alliance_id is None and related_alliance_name:
        related_alliance_id = resolve_alliance_id(related_alliance_name)

    return (
        corporation_id,
        corporation_name,
        alliance_id,
        alliance_name or "",
        related_alliance_id,
        related_alliance_name or "",
    )


def _apply_structure_updates(structure, defaults: dict) -> None:
    """Upgrade an existing recon row without wiping earlier notes."""
    changed = []
    for field, value in defaults.items():
        if value in (None, "") and field not in (
            "timer",
            "created_by",
            "reinforce_hour",
            "corporation_id",
            "related_alliance_id",
        ):
            continue
        if getattr(structure, field) != value:
            setattr(structure, field, value)
            changed.append(field)
    if changed:
        structure.save(update_fields=changed + ["updated_at"])


@transaction.atomic
def attach_structure(
    campaign: Campaign,
    *,
    name: str,
    structure_type: str,
    system_name: str,
    solar_system_id: int | None = None,
    corporation_name: str = "",
    corporation_id: int | None = None,
    alliance_name: str = "",
    alliance_id: int | None = None,
    related_alliance_name: str = "",
    related_alliance_id: int | None = None,
    status: str = StructureStatus.ANCHORED,
    source: str = StructureSource.RECON,
    timer=None,
    created_by=None,
    eve_structure_id: int | None = None,
    fitting: str = "",
    reinforce_hour: int | None = None,
) -> CampaignStructure:
    """Upsert a CampaignStructure and grow the theater around it."""
    solar_system_id, system_name = _resolve_attach_system(
        solar_system_id, system_name
    )
    (
        corporation_id,
        corporation_name,
        alliance_id,
        alliance_name,
        related_alliance_id,
        related_alliance_name,
    ) = _resolve_attach_ownership(
        corporation_name=corporation_name,
        corporation_id=corporation_id,
        alliance_name=alliance_name,
        alliance_id=alliance_id,
        related_alliance_name=related_alliance_name,
        related_alliance_id=related_alliance_id,
    )
    reinforce_hour = _normalize_reinforce_hour(reinforce_hour)

    type_id = STRUCTURE_TYPE_IDS.get(structure_type)
    ensure_campaign_system(campaign, solar_system_id, system_name)
    ensure_feed_monitoring(solar_system_id, system_name)

    defaults = {
        "corporation_id": corporation_id,
        "corporation_name": corporation_name or "",
        "alliance_name": alliance_name or "",
        "alliance_id": alliance_id,
        "related_alliance_id": related_alliance_id,
        "related_alliance_name": related_alliance_name or "",
        "type_id": type_id,
        "status": status,
        "source": source,
        "eve_structure_id": eve_structure_id,
    }
    if fitting:
        defaults["fitting"] = fitting
    if reinforce_hour is not None:
        defaults["reinforce_hour"] = reinforce_hour
    if timer is not None:
        defaults["timer"] = timer
    if created_by is not None:
        defaults["created_by"] = created_by

    structure, created = CampaignStructure.objects.update_or_create(
        campaign=campaign,
        solar_system_id=solar_system_id,
        structure_type=structure_type,
        name=name,
        defaults={
            **defaults,
            "system_name": system_name,
        },
    )
    if not created:
        _apply_structure_updates(structure, defaults)

    return structure


def attach_timer(
    campaign: Campaign,
    timer,
    created_by=None,
    *,
    fitting: str = "",
    reinforce_hour: int | None = None,
    corporation_id: int | None = None,
    related_alliance_name: str = "",
    related_alliance_id: int | None = None,
) -> CampaignStructure:
    """Link an EveStructureTimer to a campaign and upsert recon."""
    timer.campaign = campaign
    timer.save(update_fields=["campaign"])

    status = StructureStatus.REINFORCED
    if timer.state in ("anchoring", "unanchoring"):
        status = StructureStatus.ANCHORED

    return attach_structure(
        campaign,
        name=timer.name,
        structure_type=timer.type,
        system_name=timer.system_name,
        corporation_name=timer.corporation_name or "",
        corporation_id=corporation_id,
        alliance_name=timer.alliance_name or "",
        status=status,
        source=StructureSource.TIMER,
        timer=timer,
        created_by=created_by or timer.created_by,
        fitting=fitting or (getattr(timer, "fitting", None) or ""),
        reinforce_hour=reinforce_hour,
        related_alliance_name=related_alliance_name,
        related_alliance_id=related_alliance_id,
    )


def match_structure_for_killmail(
    campaign: Campaign,
    *,
    solar_system_id: int,
    ship_type_id: int | None,
    name: str = "",
) -> CampaignStructure | None:
    """Find a recon row that this killmail destroyed."""
    structure_type = structure_type_for_ship_type(ship_type_id)
    if not structure_type:
        return None

    queryset = CampaignStructure.objects.filter(
        campaign=campaign,
        solar_system_id=solar_system_id,
        structure_type=structure_type,
    ).exclude(status=StructureStatus.DESTROYED)

    if name:
        exact = queryset.filter(name__iexact=name).first()
        if exact:
            return exact

    # One structure of this type in the system is enough to soft-link.
    if queryset.count() == 1:
        return queryset.first()
    return None


def structure_matches_party(
    structure: CampaignStructure, party: CampaignParty
) -> bool:
    """True when the structure's owner or affiliated party is this party."""
    if party.kind == PartyKind.ALLIANCE:
        alliance_id = party.alliance_id
        if alliance_id is None:
            return False
        return alliance_id in (
            structure.alliance_id,
            structure.related_alliance_id,
        )
    if party.kind == PartyKind.CORPORATION:
        return (
            party.corporation_id is not None
            and party.corporation_id == structure.corporation_id
        )
    # Characters and factions do not own citadels in our recon model yet.
    return False


def structure_affiliation(
    structure: CampaignStructure,
    parties: list[CampaignParty] | None = None,
) -> str:
    """hostile / friendly / neutral from campaign parties.

    Enemy matches win over ally when both somehow apply. Affiliated alliance
    (related_alliance_*) counts the same as the legal owner alliance.
    """
    rows = (
        parties
        if parties is not None
        else list(structure.campaign.parties.all())
    )
    enemy_hit = False
    ally_hit = False
    for party in rows:
        if not structure_matches_party(structure, party):
            continue
        if party.side == PartySide.ENEMY:
            enemy_hit = True
        elif party.side == PartySide.ALLY:
            ally_hit = True
    if enemy_hit:
        return StructureAffiliation.HOSTILE
    if ally_hit:
        return StructureAffiliation.FRIENDLY
    return StructureAffiliation.NEUTRAL


def mark_destroyed(
    structure: CampaignStructure, killmail
) -> CampaignStructure:
    """Record that a recon structure died on this mail."""
    structure.status = StructureStatus.DESTROYED
    structure.destroyed_at = killmail.killmail_time or timezone.now()
    structure.killmail = killmail
    structure.source = StructureSource.KILLMAIL
    structure.save(
        update_fields=[
            "status",
            "destroyed_at",
            "killmail",
            "source",
            "updated_at",
        ]
    )
    return structure


def deactivate_unused_campaign_monitors(solar_system_id: int) -> None:
    """Turn off campaign-sourced feed rows no live campaign still needs."""
    still_needed = CampaignSystem.objects.filter(
        solar_system_id=solar_system_id,
        retired_at__isnull=True,
        campaign__status__in=["scheduled", "active"],
    ).exists()
    if still_needed:
        return

    updated = FeedMonitoredSystem.objects.filter(
        solar_system_id=solar_system_id,
        source=FeedMonitoredSystem.Source.CAMPAIGN,
        is_active=True,
    ).update(is_active=False)
    if updated:
        logger.info(
            "Deactivated campaign feed monitoring for system %s",
            solar_system_id,
        )
