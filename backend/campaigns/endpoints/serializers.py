"""Shape ORM rows into API responses."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from campaigns.models import (
    Campaign,
    CampaignEnlistment,
    CampaignKillmail,
    CampaignKillmailParticipant,
    CampaignParticipantStat,
    CampaignSystem,
    CampaignSystemSnapshot,
    KillmailOutcome,
    SystemGoal,
)
from campaigns.services import advantage, snapshots, stats
from eveonline.models import EveCorporation, EveCharacter, EvePlayer
from feed.models import FeedKillmail
from fittings.models import EveFitting


def system_summary(
    campaign_system: CampaignSystem, with_trend: bool = True
) -> dict:
    """Contest, advantage and kills, each with its own direction of travel.

    A system card has to answer one question at a glance: are we gaining
    ground here or losing it.
    """
    now = timezone.now()
    latest = (
        CampaignSystemSnapshot.objects.filter(campaign_system=campaign_system)
        .order_by("-captured_at")
        .first()
    )
    day_ago = (
        CampaignSystemSnapshot.objects.filter(
            campaign_system=campaign_system,
            captured_at__lte=now - timedelta(hours=24),
        )
        .order_by("-captured_at")
        .first()
    )

    contested = latest.contested_percent if latest else None
    contested_change = (
        round(latest.contested_percent - day_ago.contested_percent, 2)
        if latest and day_ago
        else None
    )

    mails = CampaignKillmail.objects.filter(
        campaign=campaign_system.campaign,
        solar_system_id=campaign_system.solar_system_id,
    )
    kills_24h = mails.filter(
        outcome=KillmailOutcome.KILL,
        killmail_time__gte=now - timedelta(hours=24),
    ).count()
    losses_24h = mails.filter(
        outcome=KillmailOutcome.LOSS,
        killmail_time__gte=now - timedelta(hours=24),
    ).count()
    kills_prior = mails.filter(
        outcome=KillmailOutcome.KILL,
        killmail_time__gte=now - timedelta(hours=48),
        killmail_time__lt=now - timedelta(hours=24),
    ).count()

    advantage_state = advantage.card_for(campaign_system)

    return {
        "id": campaign_system.id,
        "name": campaign_system.name,
        "solar_system_id": campaign_system.solar_system_id,
        "role": campaign_system.role,
        "goal": campaign_system.goal,
        "priority": campaign_system.priority,
        "is_fw_objective": campaign_system.is_fw_objective,
        "contested_percent": (
            round(contested, 2) if contested is not None else None
        ),
        "contested_change_24h": contested_change,
        "victory_points": latest.victory_points if latest else None,
        "victory_points_threshold": (
            latest.victory_points_threshold if latest else None
        ),
        "operational_state": latest.operational_state if latest else "unknown",
        "contested_updated_at": latest.captured_at if latest else None,
        "advantage_updated_at": advantage_state["read_at"],
        # Warzone "holder" is ESI occupier (see feed/warzone); owner is the
        # longer-lived ownership CCP flips when VP crosses the threshold.
        "occupier_faction_id": (
            latest.occupier_faction_id if latest else None
        ),
        "owner_faction_id": latest.owner_faction_id if latest else None,
        "advantage_basis": advantage_state["basis"],
        "advantage_source": advantage_state["source"],
        "advantage_our_pct": advantage_state["our_pct"],
        "advantage_enemy_pct": advantage_state["enemy_pct"],
        "advantage_net_pct": advantage_state["net_pct"],
        "advantage_age_minutes": advantage_state["reading_age_minutes"],
        "advantage_is_stale": advantage_state["is_stale"],
        "kills_24h": kills_24h,
        "losses_24h": losses_24h,
        "kills_change_24h": kills_24h - kills_prior,
        "trend": snapshots.system_trend(campaign_system) if with_trend else [],
        "status_chip": _status_chip(
            campaign_system, contested_change, kills_24h, losses_24h
        ),
    }


def _status_chip(campaign_system, contested_change, kills, losses) -> str:
    """Gaining ground, holding or losing ground, read off the trends."""
    if contested_change is None:
        return "holding"

    wants_more_contest = campaign_system.goal == SystemGoal.CAPTURE
    moving_our_way = (
        contested_change > 0.5
        if wants_more_contest
        else contested_change < -0.5
    )
    moving_their_way = (
        contested_change < -0.5
        if wants_more_contest
        else contested_change > 0.5
    )

    if moving_our_way and kills >= losses:
        return "gaining"
    if moving_their_way and losses > kills:
        return "losing"
    if moving_our_way:
        return "gaining"
    if moving_their_way:
        return "losing"
    return "holding"


def campaign_systems(
    campaign: Campaign, with_trend: bool = True
) -> list[dict]:
    rows = [
        system_summary(system, with_trend=with_trend)
        for system in campaign.systems.filter(retired_at__isnull=True)
    ]
    # Most contested first: that is where the fight is.
    return sorted(
        rows, key=lambda row: row["contested_percent"] or 0, reverse=True
    )


def list_item(campaign: Campaign, user=None) -> dict:
    totals = stats.campaign_totals(campaign)
    next_timer = (
        campaign.structure_timers.filter(timer__gte=timezone.now())
        .order_by("timer")
        .values_list("timer", flat=True)
        .first()
    )
    return {
        "id": campaign.id,
        "slug": campaign.slug,
        "name": campaign.name,
        "short_code": campaign.short_code,
        "tagline": campaign.tagline,
        "kind": campaign.kind,
        "status": campaign.status,
        "start_at": campaign.start_at,
        "end_at": campaign.end_at,
        "cover_image_url": campaign.cover_image_url,
        "systems": campaign_systems(campaign, with_trend=False),
        "areas": campaign_areas(campaign),
        "opponents": [opponent_out(row) for row in campaign.opponents.all()],
        "structures_remaining": totals["structures_remaining"],
        "structures_destroyed": totals["structures_destroyed"],
        "next_timer_at": next_timer,
        "enlisted": totals["enlisted"],
        "kills": totals["kills"],
        "isk_destroyed": totals["isk_destroyed"],
        "is_enlisted": is_enlisted(campaign, user),
    }


def area_out(area) -> dict:
    return {
        "id": area.id,
        "scope": area.scope,
        "name": area.name,
        "constellation_id": area.constellation_id,
        "region_id": area.region_id,
    }


def campaign_areas(campaign: Campaign) -> list[dict]:
    return [area_out(area) for area in campaign.areas.all()]


def opponent_out(opponent) -> dict:
    return {
        "id": opponent.id,
        "name": opponent.name,
        "ticker": opponent.ticker or "",
        "alliance_id": opponent.alliance_id,
        "corporation_id": opponent.corporation_id,
        "faction_id": opponent.faction_id,
    }


def fitting_out(row) -> dict:
    fitting = row.fitting
    ship_name = ""
    if fitting and fitting.eft_format:
        ship_name = EveFitting.ship_name_from_eft(fitting.eft_format) or ""
    return {
        "id": row.id,
        "fitting_id": fitting.id if fitting else 0,
        "name": fitting.name if fitting else "",
        "ship_name": ship_name,
        "role_label": row.role_label or "",
        "srp_eligible": row.srp_eligible,
        "order": row.order,
    }


def campaign_fittings(campaign: Campaign) -> list[dict]:
    return [
        fitting_out(row)
        for row in campaign.fittings.select_related("fitting").all()
    ]


def structure_out(structure) -> dict:
    timer = structure.timer
    return {
        "id": structure.id,
        "name": structure.name,
        "structure_type": structure.structure_type,
        "type_id": structure.type_id,
        "solar_system_id": structure.solar_system_id,
        "system_name": structure.system_name,
        "corporation_id": structure.corporation_id,
        "corporation_name": structure.corporation_name or "",
        "alliance_id": structure.alliance_id,
        "alliance_name": structure.alliance_name or "",
        "related_alliance_id": structure.related_alliance_id,
        "related_alliance_name": structure.related_alliance_name or "",
        "status": structure.status,
        "source": structure.source,
        "fitting": structure.fitting or "",
        "reinforce_hour": structure.reinforce_hour,
        "timer_id": timer.id if timer else None,
        "timer_at": timer.timer if timer else None,
        "destroyed_at": structure.destroyed_at,
        "killmail_id": (
            structure.killmail.killmail_id if structure.killmail_id else None
        ),
    }


def is_enlisted(campaign: Campaign, user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return campaign.enlistments.filter(user=user, status="active").exists()


COMPLEX_SIZES = ("Scout", "Small", "Medium", "Large", "Open", "FRF")
# When a payout tier fits several variants, the plainest one wins: NVY-1
# plexes are by far the most run, then NVY-5, then the advanced variants.
VARIANT_PREFERENCE = ("NVY-1", "NVY-5", "ADV-1", "ADV-5", "ELT-5", "")


def complex_size(candidates: list | None) -> str:
    """One size class for a capture, picked from the inferred candidates.

    A pilot wants to read "Medium complex", not the list of variants a
    payout could have come from, so the tier is resolved to its most likely
    variant and that variant's size is what shows. The candidates stay in
    the API for the hover text.
    """
    best_rank = len(VARIANT_PREFERENCE)
    best_size = ""
    for name in candidates or []:
        name = str(name)
        size = next((s for s in COMPLEX_SIZES if name.startswith(s)), None)
        if not size:
            continue
        rank = next(
            (
                index
                for index, variant in enumerate(VARIANT_PREFERENCE)
                if variant and variant in name
            ),
            len(VARIANT_PREFERENCE) - 1,
        )
        if rank < best_rank:
            best_rank, best_size = rank, size
    return best_size


def killmail_out(mail: CampaignKillmail) -> dict:
    return {
        "killmail_id": mail.killmail_id,
        "killmail_time": mail.killmail_time,
        "outcome": mail.outcome,
        "solar_system_id": mail.solar_system_id,
        "victim_character_name": mail.victim_character_name or "",
        "victim_character_id": mail.victim_character_id,
        "victim_corporation_id": mail.victim_corporation_id,
        "victim_alliance_id": mail.victim_alliance_id,
        "victim_faction_id": mail.victim_faction_id,
        "victim_ship_type_id": mail.victim_ship_type_id,
        "killer_character_id": mail.killer_character_id,
        "killer_character_name": mail.killer_character_name or "",
        "killer_faction_id": mail.killer_faction_id,
        "isk_value": mail.isk_value,
        "enlisted_attacker_count": mail.enlisted_attacker_count,
        "is_solo": mail.is_solo,
        "is_structure": mail.is_structure,
        "is_capital": mail.is_capital,
        "structure_id": mail.structure_id,
    }


def coverage_window(campaign: Campaign, days: int = 7):
    """The last ``days`` of fighting, not the last ``days`` of wall clock.

    A campaign that finished last month, or one whose feed has been quiet
    for a week, would otherwise render an empty chart. The window ends at
    the most recent thing that happened in the campaign.
    """
    latest = (
        CampaignKillmail.objects.filter(campaign=campaign)
        .order_by("-killmail_time")
        .values_list("killmail_time", flat=True)
        .first()
    )
    anchor = min(latest or timezone.now(), timezone.now())
    anchor = max(anchor, campaign.start_at)
    return anchor - timedelta(days=days), anchor


def coverage_by_hour(campaign: Campaign, days: int = 7) -> list[dict]:
    """Enlisted activity per UTC hour against hostile activity per hour.

    The hole where they play and we do not is the point of this chart.
    """
    since, until = coverage_window(campaign, days)

    ours = CampaignKillmailParticipant.objects.filter(
        killmail__campaign=campaign,
        killmail__killmail_time__gte=since,
        killmail__killmail_time__lte=until,
        enlisted=True,
    ).values_list("killmail__killmail_time", flat=True)
    our_hours: dict[int, set] = {hour: set() for hour in range(24)}
    for moment in ours:
        our_hours[moment.hour].add(moment.date())

    hostile_counts = {hour: 0 for hour in range(24)}
    hostile = FeedKillmail.objects.filter(
        solar_system_id__in=campaign.system_ids(),
        killmail_time__gte=since,
        killmail_time__lte=until,
    ).values_list("killmail_time", flat=True)
    for moment in hostile:
        hostile_counts[moment.hour] += 1

    return [
        {
            "hour": hour,
            "our_active_days": len(our_hours[hour]),
            "hostile_activity": hostile_counts[hour],
        }
        for hour in range(24)
    ]


def roster_rows(campaign: Campaign) -> list[dict]:
    """The roster, in a handful of queries rather than three per pilot."""
    enlistments = list(
        CampaignEnlistment.objects.filter(campaign=campaign, status="active")
        .select_related("user")
        .annotate(
            included=Count(
                "characters", filter=Q(characters__included_until__isnull=True)
            )
        )
    )
    if not enlistments:
        return []

    user_ids = [enlistment.user_id for enlistment in enlistments]

    players = {
        player.user_id: player
        for player in EvePlayer.objects.filter(
            user_id__in=user_ids
        ).select_related("primary_character")
    }
    stats_by_user = {
        row.user_id: row
        for row in CampaignParticipantStat.objects.filter(campaign=campaign)
    }
    corporation_names = dict(
        EveCorporation.objects.filter(
            corporation_id__in=[
                player.primary_character.corporation_id
                for player in players.values()
                if player.primary_character
                and player.primary_character.corporation_id
            ]
        ).values_list("corporation_id", "name")
    )
    tracked_by_user = dict(
        EveCharacter.objects.filter(
            user_id__in=user_ids,
            token__scopes__name="esi-characters.read_notifications.v1",
        )
        .values_list("user_id")
        .annotate(n=Count("id", distinct=True))
        .values_list("user_id", "n")
    )

    rows = []
    for enlistment in enlistments:
        player = players.get(enlistment.user_id)
        primary = player.primary_character if player else None
        stat = stats_by_user.get(enlistment.user_id)

        rows.append(
            {
                "user_id": enlistment.user_id,
                "username": enlistment.user.username,
                "primary_character": (
                    primary.character_name if primary else ""
                ),
                "character_id": primary.character_id if primary else None,
                "corporation_id": primary.corporation_id if primary else None,
                "corporation_name": (
                    corporation_names.get(primary.corporation_id, "")
                    if primary
                    else ""
                ),
                "prime_time": (player.prime_time if player else "") or "",
                "observed_prime_time": (
                    stat.observed_prime_time if stat else ""
                ),
                "last_active_day": stat.last_active_day if stat else None,
                "streak_days": stat.streak_days if stat else 0,
                "points": stat.points if stat else 0,
                "characters_included": enlistment.included,
                "characters_tracked": tracked_by_user.get(
                    enlistment.user_id, 0
                ),
            }
        )

    return sorted(rows, key=lambda row: row["points"], reverse=True)
