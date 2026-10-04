"""Attribute killmails to campaigns.

The zKill stream is the fast path but never the only one: a 48-hour sweep, a
per-character recent-killmails poll and the LP kill-payout cross-check each
recover a mail the stream missed. Every campaign mail records which sources
saw it and which saw it first.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from feed.helpers.capital_ships import is_capital_ship_type
from feed.models import FeedKillmail

from campaigns.helpers import CampaignRoster, counting_campaigns
from campaigns.models import (
    Campaign,
    CampaignKillmail,
    CampaignKillmailParticipant,
    CampaignSystem,
    KillmailOutcome,
)
from campaigns.services import structures as structure_service

logger = logging.getLogger(__name__)

POD_GROUP_TYPE_IDS = {670, 33328}  # Capsule, Capsule - Genolution


def attribute_feed_killmail(
    feed_killmail, source: str = "stream", rosters: dict | None = None
) -> int:
    """Attribute one FeedKillmail row to every campaign that wants it.

    ``rosters`` lets a caller processing many mails load each campaign's
    roster once instead of once per mail. Returns how many campaigns the mail
    landed in.
    """
    raw = feed_killmail.raw_killmail or {}
    zkb = feed_killmail.zkb_meta or {}
    moment = feed_killmail.killmail_time
    count = 0

    for campaign in counting_campaigns(feed_killmail.solar_system_id, moment):
        roster = _roster_for(campaign, rosters)
        if _attribute_one(campaign, feed_killmail, raw, zkb, source, roster):
            count += 1
    return count


def _roster_for(campaign: Campaign, rosters: dict | None) -> CampaignRoster:
    if rosters is None:
        return CampaignRoster(campaign)
    if campaign.id not in rosters:
        rosters[campaign.id] = CampaignRoster(campaign)
    return rosters[campaign.id]


def _attribute_one(
    campaign: Campaign,
    feed_killmail,
    raw: dict,
    zkb: dict,
    source: str,
    roster: CampaignRoster,
) -> bool:
    moment = feed_killmail.killmail_time
    if not roster:
        return False

    victim = raw.get("victim") or {}
    attackers = raw.get("attackers") or []

    character_ids = [victim.get("character_id")] + [
        attacker.get("character_id") for attacker in attackers
    ]
    included = roster.resolve(character_ids, moment)
    if not included:
        return False

    victim_character_id = victim.get("character_id")
    victim_is_ours = victim_character_id in included
    our_attackers = [
        a
        for a in attackers
        if a.get("character_id") and a.get("character_id") in included
    ]

    if victim_is_ours and our_attackers:
        outcome = KillmailOutcome.AWOX
    elif victim_is_ours:
        outcome = KillmailOutcome.LOSS
    else:
        outcome = KillmailOutcome.KILL

    campaign_system = CampaignSystem.objects.filter(
        campaign=campaign,
        solar_system_id=feed_killmail.solar_system_id,
        retired_at__isnull=True,
    ).first()
    has_structure = campaign.structures.filter(
        solar_system_id=feed_killmail.solar_system_id
    ).exists()
    # Ops theaters (is_fw_objective=False) do not score ship kills unless a
    # campaign structure sits in the system (citadel bash path).
    fw_objective = bool(campaign_system and campaign_system.is_fw_objective)
    if not fw_objective and not has_structure:
        return False

    ship_type_id = victim.get("ship_type_id")
    is_pod = ship_type_id in POD_GROUP_TYPE_IDS
    is_structure = structure_service.is_structure_type(ship_type_id)
    is_capital = (not is_structure) and is_capital_ship_type(ship_type_id)
    matched_structure = structure_service.match_structure_for_killmail(
        campaign,
        solar_system_id=feed_killmail.solar_system_id,
        ship_type_id=ship_type_id,
    )
    killer = final_blow(attackers)

    with transaction.atomic():
        mail, created = CampaignKillmail.objects.get_or_create(
            campaign=campaign,
            killmail_id=feed_killmail.killmail_id,
            defaults={
                "killmail_hash": feed_killmail.hash or "",
                "killmail_time": moment,
                "solar_system_id": feed_killmail.solar_system_id,
                "victim_character_id": victim_character_id,
                "victim_corporation_id": victim.get("corporation_id"),
                "victim_alliance_id": victim.get("alliance_id"),
                "victim_faction_id": victim.get("faction_id"),
                "victim_ship_type_id": ship_type_id,
                "killer_character_id": killer.get("character_id"),
                "killer_faction_id": killer.get("faction_id"),
                "isk_value": int(zkb.get("totalValue") or 0),
                "is_pod": is_pod,
                "is_solo": bool(zkb.get("solo")),
                "is_structure": is_structure,
                "is_capital": is_capital,
                "structure": matched_structure,
                "attacker_count": len(attackers),
                "enlisted_attacker_count": len(our_attackers),
                "outcome": outcome,
                "sources": [source],
                "first_seen_via": source,
                "on_zkillboard": source == "stream",
            },
        )

        if not created:
            changed = False
            update_fields = []
            if source not in (mail.sources or []):
                mail.sources = list(mail.sources or []) + [source]
                update_fields.append("sources")
                changed = True
            # Re-resolve: characters move between users and pilots enlist
            # mid-campaign, so a sweep can legitimately change the outcome.
            if mail.outcome != outcome or (
                mail.enlisted_attacker_count != len(our_attackers)
            ):
                mail.outcome = outcome
                mail.enlisted_attacker_count = len(our_attackers)
                update_fields.extend(["outcome", "enlisted_attacker_count"])
                changed = True
            if (
                mail.is_structure != is_structure
                or mail.is_capital != is_capital
            ):
                mail.is_structure = is_structure
                mail.is_capital = is_capital
                update_fields.extend(["is_structure", "is_capital"])
                changed = True
            if matched_structure and mail.structure_id != matched_structure.id:
                mail.structure = matched_structure
                update_fields.append("structure")
                changed = True
            if changed:
                mail.save(update_fields=update_fields)

        _write_participants(mail, victim, attackers, included)

        if (
            created
            and matched_structure
            and outcome == KillmailOutcome.KILL
            and is_structure
        ):
            structure_service.mark_destroyed(matched_structure, mail)

    return created


def final_blow(attackers: list) -> dict:
    """The attacker who landed the final blow, else the top damage dealer."""
    for attacker in attackers:
        if attacker.get("final_blow"):
            return attacker
    if attackers:
        return max(attackers, key=lambda row: int(row.get("damage_done") or 0))
    return {}


def _write_participants(mail, victim: dict, attackers: list, included: dict):
    """Store one row per character on the mail that belongs to us."""
    rows = []
    victim_character_id = victim.get("character_id")
    if victim_character_id and victim_character_id in included:
        rows.append(
            {
                "character_id": victim_character_id,
                "user": included[victim_character_id],
                "enlisted": True,
                "role": "victim",
                "ship_type_id": victim.get("ship_type_id"),
                "damage_done": 0,
                "final_blow": False,
            }
        )
    for attacker in attackers:
        character_id = attacker.get("character_id")
        if not character_id or character_id not in included:
            continue
        rows.append(
            {
                "character_id": character_id,
                "user": included[character_id],
                "enlisted": True,
                "role": "attacker",
                "ship_type_id": attacker.get("ship_type_id"),
                "damage_done": int(attacker.get("damage_done") or 0),
                "final_blow": bool(attacker.get("final_blow")),
            }
        )

    for row in rows:
        CampaignKillmailParticipant.objects.update_or_create(
            killmail=mail,
            character_id=row["character_id"],
            defaults=row,
        )


def sweep_campaign(campaign: Campaign, hours: int = 48) -> dict:
    """Re-attribute recent feed killmails in one campaign's systems."""
    since = timezone.now() - timedelta(hours=hours)
    system_ids = set(campaign.system_ids())
    if not system_ids:
        return {"scanned": 0, "attributed": 0}

    scanned = 0
    attributed = 0
    rosters: dict = {}
    queryset = FeedKillmail.objects.filter(
        solar_system_id__in=system_ids, killmail_time__gte=since
    ).iterator()
    for feed_killmail in queryset:
        scanned += 1
        attributed += attribute_feed_killmail(
            feed_killmail, source="sweep", rosters=rosters
        )
    return {"scanned": scanned, "attributed": attributed}


def sweep_recent(hours: int = 48) -> dict:
    """Re-attribute every feed killmail in campaign systems for a window.

    Cheap insurance against a mail that arrived while a campaign was being
    created, a character that changed hands, or a pilot who enlisted after
    the fight.
    """
    since = timezone.now() - timedelta(hours=hours)
    campaigns = Campaign.objects.filter(status__in=["scheduled", "active"])
    system_ids = set()
    for campaign in campaigns:
        system_ids.update(campaign.system_ids())
    if not system_ids:
        return {"scanned": 0, "attributed": 0}

    scanned = 0
    attributed = 0
    rosters: dict = {}
    queryset = FeedKillmail.objects.filter(
        solar_system_id__in=system_ids, killmail_time__gte=since
    ).iterator()
    for feed_killmail in queryset:
        scanned += 1
        attributed += attribute_feed_killmail(
            feed_killmail, source="sweep", rosters=rosters
        )
    return {"scanned": scanned, "attributed": attributed}
