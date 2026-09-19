"""Materialise per-pilot days, then read every board from those rows.

Boards are recomputed from source rather than incremented, so a late mail, a
re-resolved character or a corrected outcome never leaves a stale total.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone

from campaigns.helpers import (
    campaign_day,
    campaign_week_start,
    day_bounds,
)
from campaigns.models import (
    Campaign,
    CampaignAdvantageReading,
    CampaignKillmail,
    CampaignKillmailParticipant,
    CampaignParticipantDay,
    CampaignParticipantStat,
    CampaignSiteCompletion,
    KillmailOutcome,
    SiteKind,
    SystemRole,
)
from campaigns.services import scoring
from feed.models import FeedKillmail

logger = logging.getLogger(__name__)

BOARD_METRICS = {
    "points": "points",
    "kills": "kills",
    "isk": "isk_destroyed",
    "sites": "complexes",
    "advantage": "advantage_generated",
    "fleets": "fleets_attended",
    "supply": "supply_isk_delivered",
}


def _blank_row() -> dict:
    return {
        "kills": 0,
        "losses": 0,
        "solo_kills": 0,
        "final_blows": 0,
        "gang_kills": 0,
        "isk_destroyed": 0,
        "isk_lost": 0,
        "complexes": 0,
        "advantage_sites": 0,
        "supply_caches": 0,
        "battlefields": 0,
        "advantage_generated": 0.0,
        "enemy_advantage_removed": 0.0,
        "advantage_readings": 0,
        "fleets_attended": 0,
        "points": 0.0,
        "site_index": 0,
    }


def _add_killmails(campaign, rows: dict, start, end) -> None:
    """Fold every mail an enlisted pilot was on into their day row."""
    participants = (
        CampaignKillmailParticipant.objects.filter(
            killmail__campaign=campaign,
            killmail__killmail_time__gte=start,
            killmail__killmail_time__lt=end,
            enlisted=True,
            user__isnull=False,
        )
        .select_related("killmail")
        .order_by("killmail__killmail_time")
    )

    for participant in participants:
        mail = participant.killmail
        row = rows.setdefault(participant.user_id, _blank_row())
        multiplier = scoring.day_multiplier(campaign, mail.killmail_time.hour)

        if (
            mail.outcome == KillmailOutcome.KILL
            and participant.role == "attacker"
        ):
            # Pods are listed in the killfeed but never scored.
            if mail.is_pod:
                continue
            row["kills"] += 1
            row["isk_destroyed"] += mail.isk_value
            row["final_blows"] += int(participant.final_blow)
            row["solo_kills"] += int(mail.is_solo)
            if 2 <= mail.enlisted_attacker_count <= 10:
                row["gang_kills"] += 1
            row["points"] += (
                scoring.kill_points(
                    campaign,
                    enlisted_on_mail=max(mail.enlisted_attacker_count, 1),
                    final_blow=participant.final_blow,
                    solo=mail.is_solo,
                    in_fleet=mail.fleet_id is not None,
                    isk_value=mail.isk_value,
                )
                * multiplier
            )
        elif (
            mail.outcome == KillmailOutcome.LOSS
            and participant.role == "victim"
        ):
            row["losses"] += 1
            row["isk_lost"] += mail.isk_value
            row["points"] += scoring.loss_points(
                campaign, in_fleet_or_gang=mail.fleet_id is not None
            )


SITE_COUNTERS = {
    SiteKind.COMPLEX: "complexes",
    SiteKind.SUPPLY_CACHE: "supply_caches",
    SiteKind.BATTLEFIELD: "battlefields",
    SiteKind.ADVANTAGE_SITE: "advantage_sites",
    SiteKind.RENDEZVOUS_POINT: "advantage_sites",
    SiteKind.PROPAGANDA_BEACON: "advantage_sites",
    SiteKind.LISTENING_OUTPOST: "advantage_sites",
}


def _add_sites(campaign, rows: dict, start, end) -> None:
    """Fold site completions in, with the per-day soft cap."""
    primary_system_ids = set(
        campaign.systems.filter(role=SystemRole.PRIMARY).values_list(
            "id", flat=True
        )
    )

    completions = CampaignSiteCompletion.objects.filter(
        campaign=campaign,
        occurred_at__gte=start,
        occurred_at__lt=end,
        user__isnull=False,
    ).order_by("occurred_at")

    for completion in completions:
        counter = SITE_COUNTERS.get(completion.site_kind)
        if not counter:
            continue

        row = rows.setdefault(completion.user_id, _blank_row())
        row[counter] += 1

        generated, removed = completion.advantage_delta
        row["advantage_generated"] += generated
        row["enemy_advantage_removed"] += removed

        row["points"] += scoring.site_points(
            campaign,
            site_kind=completion.site_kind,
            base_lp_tier=(
                completion.complex.base_lp_tier if completion.complex else None
            ),
            primary_system=(
                completion.campaign_system_id in primary_system_ids
            ),
            index_today=row["site_index"],
        ) * scoring.day_multiplier(campaign, completion.occurred_at.hour)
        row["site_index"] += 1


def _add_advantage_readings(campaign, rows: dict, start, end) -> None:
    readings = CampaignAdvantageReading.objects.filter(
        campaign_system__campaign=campaign,
        reported_at__gte=start,
        reported_at__lt=end,
        status="accepted",
        reported_by__isnull=False,
    )
    points = scoring.weights(campaign)["advantage_reading"]
    for reading in readings:
        row = rows.setdefault(reading.reported_by_id, _blank_row())
        row["advantage_readings"] += 1
        row["points"] += points


ACTIVITY_FIELDS = (
    "kills",
    "losses",
    "complexes",
    "advantage_sites",
    "supply_caches",
    "battlefields",
    "advantage_readings",
    "fleets_attended",
)


def materialise_day(campaign: Campaign, day: date) -> int:
    """Rebuild every pilot's row for one campaign day."""
    start, end = day_bounds(day)
    rows: dict[int, dict] = {}

    _add_killmails(campaign, rows, start, end)
    _add_sites(campaign, rows, start, end)
    _add_advantage_readings(campaign, rows, start, end)

    active_day_points = scoring.weights(campaign)["active_day"]
    written = 0

    for user_id, values in rows.items():
        values.pop("site_index", None)
        # A day never goes negative: a bad night should not punish undocking.
        points = int(max(0, round(values.pop("points"))))
        active = any(values[field] for field in ACTIVITY_FIELDS)
        if active:
            points += active_day_points

        CampaignParticipantDay.objects.update_or_create(
            campaign=campaign,
            user_id=user_id,
            day=day,
            defaults={**values, "points": points, "active": active},
        )
        written += 1

    return written


def materialise_recent(campaign: Campaign, days: int = 2) -> int:
    today = campaign_day()
    written = 0
    for offset in range(days):
        written += materialise_day(campaign, today - timedelta(days=offset))
    return written


def rebuild_stats(campaign: Campaign) -> int:
    """Roll the day rows up per pilot, including streaks and ranks."""
    today = campaign_day()
    user_ids = (
        CampaignParticipantDay.objects.filter(campaign=campaign)
        .values_list("user_id", flat=True)
        .distinct()
    )

    updated = 0
    for user_id in user_ids:
        days = list(
            CampaignParticipantDay.objects.filter(
                campaign=campaign, user_id=user_id
            ).order_by("-day")
        )
        totals = {
            "points": sum(d.points for d in days),
            "kills": sum(d.kills for d in days),
            "losses": sum(d.losses for d in days),
            "isk_destroyed": sum(d.isk_destroyed for d in days),
            "isk_lost": sum(d.isk_lost for d in days),
            "complexes": sum(d.complexes for d in days),
            "advantage_sites": sum(d.advantage_sites for d in days),
            "advantage_generated": sum(d.advantage_generated for d in days),
            "fleets_attended": sum(d.fleets_attended for d in days),
            "standing_fleet_minutes": sum(
                d.standing_fleet_minutes for d in days
            ),
            "active_days": sum(1 for d in days if d.active),
        }

        streak, best = _streaks([d.day for d in days if d.active], today)
        last_active = next((d.day for d in days if d.active), None)

        CampaignParticipantStat.objects.update_or_create(
            campaign=campaign,
            user_id=user_id,
            defaults={
                **totals,
                "streak_days": streak,
                "best_streak_days": best,
                "last_active_day": last_active,
            },
        )
        updated += 1

    for index, stat in enumerate(
        CampaignParticipantStat.objects.filter(campaign=campaign).order_by(
            "-points"
        ),
        start=1,
    ):
        if stat.rank_points != index:
            stat.rank_points = index
            stat.save(update_fields=["rank_points"])

    return updated


def _streaks(active_days: list[date], today: date) -> tuple[int, int]:
    """Current and best run of consecutive active campaign days."""
    if not active_days:
        return 0, 0
    days = sorted(set(active_days), reverse=True)

    current = 0
    cursor = today
    # Yesterday still counts: the day is not over until 11:00 UTC.
    if days[0] not in (today, today - timedelta(days=1)):
        current = 0
    else:
        cursor = days[0]
        for day in days:
            if day == cursor:
                current += 1
                cursor -= timedelta(days=1)
            elif day < cursor:
                break

    best = 1
    run = 1
    ordered = sorted(set(active_days))
    for previous, day in zip(ordered, ordered[1:]):
        if (day - previous).days == 1:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return current, max(best, current)


def leaderboard(
    campaign: Campaign,
    metric: str = "points",
    period: str = "week",
    limit: int = 25,
) -> list[dict]:
    """Every board reads the same day rows; only the window changes."""
    field = BOARD_METRICS.get(metric, "points")
    queryset = CampaignParticipantDay.objects.filter(campaign=campaign)

    if period == "week":
        week_start = campaign_week_start()
        queryset = queryset.filter(day__gte=week_start)
    elif period == "rolling7":
        queryset = queryset.filter(day__gte=campaign_day() - timedelta(days=7))

    rows = (
        queryset.values("user_id", "user__username")
        .annotate(value=Sum(field), points=Sum("points"))
        .order_by("-value")[:limit]
    )

    return [
        {
            "rank": index,
            "user_id": row["user_id"],
            "username": row["user__username"],
            "value": float(row["value"] or 0),
            "points": int(row["points"] or 0),
        }
        for index, row in enumerate(rows, start=1)
    ]


def campaign_totals(campaign: Campaign) -> dict:
    """The stat bar under the hero."""
    mails = CampaignKillmail.objects.filter(campaign=campaign)
    kills = mails.filter(outcome=KillmailOutcome.KILL)
    losses = mails.filter(outcome=KillmailOutcome.LOSS)
    sites = CampaignSiteCompletion.objects.filter(campaign=campaign)

    advantage = sum(
        completion.advantage_delta[0] for completion in sites.only("site_kind")
    )

    return {
        "enlisted": campaign.enlistments.filter(status="active").count(),
        "kills": kills.count(),
        "losses": losses.count(),
        "isk_destroyed": kills.aggregate(v=Sum("isk_value"))["v"] or 0,
        "isk_lost": losses.aggregate(v=Sum("isk_value"))["v"] or 0,
        "complexes": sites.filter(site_kind=SiteKind.COMPLEX).count(),
        "advantage_sites": sites.exclude(site_kind=SiteKind.COMPLEX).count(),
        "advantage_generated": round(advantage, 1),
        "active_today": CampaignParticipantDay.objects.filter(
            campaign=campaign, day=campaign_day(), active=True
        ).count(),
    }


def active_recently(campaign: Campaign, minutes: int = 30) -> int:
    """Pilots seen doing something in the last half hour."""
    since = timezone.now() - timedelta(minutes=minutes)
    from_kills = set(
        CampaignKillmailParticipant.objects.filter(
            killmail__campaign=campaign,
            killmail__killmail_time__gte=since,
            enlisted=True,
            user__isnull=False,
        ).values_list("user_id", flat=True)
    )
    from_sites = set(
        CampaignSiteCompletion.objects.filter(
            campaign=campaign, occurred_at__gte=since, user__isnull=False
        ).values_list("user_id", flat=True)
    )
    return len(from_kills | from_sites)


def system_heat(campaign: Campaign, hours: int = 1) -> int:
    """All mails in the campaign systems in the last hour, ours or not."""
    since = timezone.now() - timedelta(hours=hours)
    return FeedKillmail.objects.filter(
        solar_system_id__in=campaign.system_ids(), killmail_time__gte=since
    ).count()


def week_summary(campaign: Campaign) -> dict:
    """The one-line result the Thursday post is built from."""
    week_start = campaign_week_start()
    rows = CampaignParticipantDay.objects.filter(
        campaign=campaign, day__gte=week_start
    )
    return {
        "week_start": week_start.isoformat(),
        "kills": rows.aggregate(v=Sum("kills"))["v"] or 0,
        "complexes": rows.aggregate(v=Sum("complexes"))["v"] or 0,
        "points": rows.aggregate(v=Sum("points"))["v"] or 0,
        "active_pilots": rows.filter(active=True)
        .values("user_id")
        .distinct()
        .count(),
    }
