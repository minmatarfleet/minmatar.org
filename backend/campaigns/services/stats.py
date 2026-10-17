"""Materialise per-pilot days, then read every board from those rows.

Boards are recomputed from source rather than incremented, so a late mail, a
re-resolved character or a corrected outcome never leaves a stale total.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from campaigns.constants import ADVANTAGE_DELTA_BY_SITE_KIND
from campaigns.helpers import (
    campaign_day,
    campaign_week_start,
    day_bounds,
    week_start_for,
)
from campaigns.models import (
    Campaign,
    CampaignAdvantageReading,
    CampaignDailyOrder,
    CampaignKillmail,
    CampaignKillmailParticipant,
    CampaignOrderProgress,
    CampaignParticipantDay,
    CampaignParticipantStat,
    CampaignSiteCompletion,
    KillmailOutcome,
    SiteKind,
    SystemRole,
)
from campaigns.services import fleets, scoring
from campaigns.services.prime_time import observed_activity
from eveonline.helpers.characters.identity import primary_refs_for_users
from eveonline.models import EveCorporation, EvePlayer
from feed.models import FeedKillmail

logger = logging.getLogger(__name__)

BOARD_METRICS = {
    "kills": "kills",
    "isk": "isk_destroyed",
    "sites": "complexes",
    "advantage": "advantage_generated",
    "fleets": "fleets_attended",
    "fcs": "fleets_led",
    "structures": "structure_kills",
    "capitals": "capital_kills",
    # "supply" arrives with the community layer, which writes
    # supply_isk_delivered. Offering the board before then would be a
    # permanently empty column.
}


def _blank_row() -> dict:
    return {
        "kills": 0,
        "losses": 0,
        "solo_kills": 0,
        "final_blows": 0,
        "gang_kills": 0,
        "structure_kills": 0,
        "structure_losses": 0,
        "capital_kills": 0,
        "capital_losses": 0,
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
        "fleets_led": 0,
        "gangs_led": 0,
        "standing_fleet_minutes": 0,
        "standing_fleet_day": False,
        "orders_completed": 0,
        "points": 0.0,
        "site_index": 0,
    }


def owned_day_counters() -> dict:
    """The counters ``materialise_day`` computes, at their empty value.

    The community-layer columns are written elsewhere and are deliberately
    absent: clearing a withdrawn day is not licence to clear someone else's
    numbers.
    """
    return {
        field: default
        for field, default in _blank_row().items()
        if field not in ("site_index", "points")
    }


def _add_killmails(campaign, rows: dict, start, end) -> None:
    """Fold every mail an enlisted pilot was on into their day row.

    A pilot counts once per mail however many of their characters were on
    it, so a multiboxer's eight alts on one kill are one kill, scored as one
    pilot on the mail.
    """
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

    # {(mail id, user id, role): (mail, final blow by any of their chars)}
    pilots_on_mails: dict[tuple, tuple] = {}
    attackers_by_mail: dict[int, set] = {}
    for participant in participants:
        key = (participant.killmail_id, participant.user_id, participant.role)
        _, final_blow = pilots_on_mails.get(key, (None, False))
        pilots_on_mails[key] = (
            participant.killmail,
            final_blow or participant.final_blow,
        )
        if participant.role == "attacker":
            attackers_by_mail.setdefault(participant.killmail_id, set()).add(
                participant.user_id
            )

    gang_size_max = scoring.weights(campaign)["gang_size_max"]

    for (mail_id, user_id, role), (
        mail,
        final_blow,
    ) in pilots_on_mails.items():
        row = rows.setdefault(user_id, _blank_row())
        multiplier = scoring.day_multiplier(campaign, mail.killmail_time.hour)

        # Pods are listed in the killfeed but never scored, on either side:
        # the ship loss already cost the pilot.
        if mail.is_pod:
            continue

        if mail.outcome == KillmailOutcome.KILL and role == "attacker":
            pilots_on_mail = len(attackers_by_mail[mail_id])
            row["kills"] += 1
            row["isk_destroyed"] += mail.isk_value
            row["final_blows"] += int(final_blow)
            row["solo_kills"] += int(mail.is_solo)
            if mail.is_structure:
                row["structure_kills"] += 1
            if mail.is_capital:
                row["capital_kills"] += 1
            if 2 <= pilots_on_mail <= gang_size_max:
                row["gang_kills"] += 1
            row["points"] += (
                scoring.kill_points(
                    campaign,
                    enlisted_on_mail=pilots_on_mail,
                    final_blow=final_blow,
                    solo=mail.is_solo,
                    in_fleet=mail.fleet_id is not None,
                    isk_value=mail.isk_value,
                )
                * multiplier
            )
        elif mail.outcome == KillmailOutcome.LOSS and role == "victim":
            row["losses"] += 1
            row["isk_lost"] += mail.isk_value
            if mail.is_structure:
                row["structure_losses"] += 1
            if mail.is_capital:
                row["capital_losses"] += 1
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

    # An unconfirmed event code is shown on the site list but must never
    # move anyone's standing, so it is excluded here entirely.
    completions = CampaignSiteCompletion.objects.filter(
        campaign=campaign,
        occurred_at__gte=start,
        occurred_at__lt=end,
        user__isnull=False,
        scored=True,
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
    ).order_by("reported_at")

    points = scoring.weights(campaign)["advantage_reading"]
    # Re-reporting the same system every minute helps nobody, so only the
    # first reading per system per pilot in each two-hour block scores.
    scored_slots: set[tuple] = set()

    for reading in readings:
        row = rows.setdefault(reading.reported_by_id, _blank_row())
        row["advantage_readings"] += 1
        slot = (
            reading.reported_by_id,
            reading.campaign_system_id,
            int(reading.reported_at.timestamp() // (2 * 3600)),
        )
        if slot in scored_slots:
            continue
        scored_slots.add(slot)
        row["points"] += points


def _add_fleets(campaign, rows: dict, day) -> None:
    """Fleet time only counts through fleets somebody attached to a campaign."""
    weights = scoring.weights(campaign)

    for user_id, values in fleets.attendance_for_day(campaign, day).items():
        row = rows.setdefault(user_id, _blank_row())
        row["fleets_attended"] += values["attended"]
        row["fleets_led"] += values["led"]
        row["gangs_led"] += values["gangs_led"]
        row["standing_fleet_minutes"] += values["standing_minutes"]
        row["standing_fleet_day"] = (
            row["standing_fleet_day"] or values["standing_day"]
        )

        # A fleet that reached a primary system is worth more than one that
        # never left the staging system.
        in_primary = values["attended_primary"]
        elsewhere = values["attended"] - in_primary
        row["points"] += in_primary * weights["fleet_attended_primary"]
        row["points"] += elsewhere * weights["fleet_attended"]
        row["points"] += values["led"] * weights["fleet_led"]
        row["points"] += values["gangs_led"] * weights["gang_led"]
        if values["standing_day"]:
            row["points"] += weights["standing_fleet_day"]


def _add_orders(campaign, rows: dict, day) -> None:
    """Orders are only worth points once attribution says they were done."""
    weights = scoring.weights(campaign)
    weekly = CampaignDailyOrder.Kind.WEEKLY_ACTIVE
    start, end = day_bounds(day)
    # Daily orders count on the day they were issued for. The weekly order
    # is issued on the day the week opens but can only be finished later in
    # the week, so it counts on the day it was completed.
    completed = (
        CampaignOrderProgress.objects.filter(
            order__campaign=campaign, completed_at__isnull=False
        )
        .filter(
            (Q(order__day=day) & ~Q(order__kind=weekly))
            | Q(
                order__kind=weekly,
                completed_at__gte=start,
                completed_at__lt=end,
            )
        )
        .select_related("order")
    )

    per_user: dict[int, int] = {}
    for progress in completed:
        row = rows.setdefault(progress.user_id, _blank_row())
        row["orders_completed"] += 1
        row["points"] += progress.order.points
        if progress.order.kind != weekly:
            per_user[progress.user_id] = per_user.get(progress.user_id, 0) + 1

    if not per_user:
        return

    # The full set is the day's own orders.
    total_today = (
        CampaignDailyOrder.objects.filter(campaign=campaign, day=day)
        .exclude(kind=weekly)
        .count()
    )
    for user_id, done in per_user.items():
        if total_today and done >= total_today:
            rows[user_id]["points"] += weights["order_full_set"]


WAYS_OF_CONTRIBUTING = (
    ("kills", "losses"),
    ("complexes", "advantage_sites", "supply_caches", "battlefields"),
    ("fleets_attended", "standing_fleet_minutes"),
    ("advantage_readings",),
    ("supply_isk_delivered",),
)


def _ways_scored_this_week(campaign, user_id: int, day, today: dict) -> int:
    """How many different kinds of work a pilot did this campaign week."""
    week_start = week_start_for(day)
    earlier = CampaignParticipantDay.objects.filter(
        campaign=campaign, user_id=user_id, day__gte=week_start, day__lte=day
    ).values(*[field for group in WAYS_OF_CONTRIBUTING for field in group])

    totals = {
        field: today.get(field, 0)
        for group in WAYS_OF_CONTRIBUTING
        for field in group
    }
    for record in earlier:
        for field, value in record.items():
            totals[field] = totals.get(field, 0) + (value or 0)

    return sum(
        1
        for group in WAYS_OF_CONTRIBUTING
        if any(totals.get(field) for field in group)
    )


ACTIVITY_FIELDS = (
    "kills",
    "losses",
    "complexes",
    "advantage_sites",
    "supply_caches",
    "battlefields",
    "advantage_readings",
    "fleets_attended",
    "orders_completed",
)


def materialise_day(campaign: Campaign, day: date) -> int:
    """Rebuild every pilot's row for one campaign day.

    The contribution-mix bonus is read from this week's earlier day rows, so
    those have to already be correct. Use ``materialise_days`` for a window;
    it sorts.
    """
    start, end = day_bounds(day)
    rows: dict[int, dict] = {}

    _add_killmails(campaign, rows, start, end)
    _add_sites(campaign, rows, start, end)
    _add_advantage_readings(campaign, rows, start, end)
    _add_fleets(campaign, rows, day)
    _add_orders(campaign, rows, day)

    active_day_points = scoring.weights(campaign)["active_day"]
    written = 0

    for user_id, values in rows.items():
        values.pop("site_index", None)
        raw_points = values.pop("points")
        active = any(values[field] for field in ACTIVITY_FIELDS)

        if active:
            raw_points += active_day_points
            ways = _ways_scored_this_week(campaign, user_id, day, values)
            raw_points *= 1 + scoring.contribution_mix_bonus(campaign, ways)

        # A day never goes negative: a bad night should not punish undocking.
        points = int(max(0, round(raw_points)))

        CampaignParticipantDay.objects.update_or_create(
            campaign=campaign,
            user_id=user_id,
            day=day,
            defaults={**values, "points": points, "active": active},
        )
        written += 1

    # Recomputed, never incremented: a pilot whose only activity for the day
    # was withdrawn keeps a row, but an empty one. Only the counters this
    # function owns are cleared; the community-layer columns are written
    # elsewhere and are not ours to reset.
    CampaignParticipantDay.objects.filter(campaign=campaign, day=day).exclude(
        user_id__in=rows.keys()
    ).exclude(points=0, active=False).update(
        **owned_day_counters(), points=0, active=False
    )

    return written


def materialise_days(campaign: Campaign, days: Iterable[date]) -> int:
    """Rebuild a set of campaign days, always oldest first.

    Order matters, which is why this sorts rather than trusting the caller: a
    day's contribution-mix bonus is read from the days before it in the week,
    so walking a window backwards would score the older days as if the ones
    before them had never happened, and every later recompute would quietly change history. Prefer
    this over calling ``materialise_day`` in a loop.
    """
    written = 0
    for day in sorted(set(days)):
        written += materialise_day(campaign, day)
    return written


def materialise_recent(campaign: Campaign, days: int = 2) -> int:
    """Rebuild the last ``days`` campaign days."""
    today = campaign_day()
    return materialise_days(
        campaign, (today - timedelta(days=offset) for offset in range(days))
    )


def rebuild_stats(campaign: Campaign) -> int:
    """Roll the day rows up per pilot, including ranks."""
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

        last_active = next((d.day for d in days if d.active), None)
        active_hours, prime_time = observed_activity(campaign, user_id)

        CampaignParticipantStat.objects.update_or_create(
            campaign=campaign,
            user_id=user_id,
            defaults={
                **totals,
                "last_active_day": last_active,
                "active_hours_utc": active_hours,
                "observed_prime_time": prime_time,
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


def leaderboard(
    campaign: Campaign,
    metric: str = "kills",
    period: str = "week",
    limit: int = 25,
) -> list[dict]:
    """Every board reads the same day rows; only the window changes."""
    field = BOARD_METRICS.get(metric, "kills")
    queryset = CampaignParticipantDay.objects.filter(campaign=campaign)
    first_day = _period_first_day(period)
    if first_day:
        queryset = queryset.filter(day__gte=first_day)

    rows = queryset.values("user_id", "user__username").annotate(
        value=Sum(field)
    )
    if metric == "fcs":
        # Most pilots never lead; the FC board lists only those who did.
        rows = rows.filter(value__gt=0)
    rows = list(rows.order_by("-value")[:limit])
    primaries = primary_characters([row["user_id"] for row in rows])

    return [
        {
            "rank": index,
            "user_id": row["user_id"],
            "username": row["user__username"],
            "character_id": primaries.get(row["user_id"], (None, ""))[0],
            "character_name": primaries.get(row["user_id"], (None, ""))[1],
            "value": float(row["value"] or 0),
        }
        for index, row in enumerate(rows, start=1)
    ]


def corporation_leaderboard(
    campaign: Campaign,
    metric: str = "kills",
    period: str = "week",
    limit: int = 25,
) -> list[dict]:
    """The pilot board rolled up by each pilot's main's corporation.

    Pilots without a main share one row with no corporation. ``pilots``
    counts the pilots who put a number on the board in the window, so a
    big corporation of idle pilots doesn't read as a busy one. Kill boards
    count each mail once per corporation: thirty members on one kill is
    one kill, not thirty. The fleets board counts distinct fleets the same
    way; the pilot board counts fleet-days (see fleets.attendance_for_day).
    """
    field = BOARD_METRICS.get(metric, "kills")
    queryset = CampaignParticipantDay.objects.filter(campaign=campaign)
    first_day = _period_first_day(period)
    if first_day:
        queryset = queryset.filter(day__gte=first_day)

    # Kill boards read the mails themselves, keeping each one's id so a
    # kill shared by several members counts once for their corporation.
    # The fleets board does the same with fleet ids.
    mails_by_user: dict[int, dict[int, int]] = {}
    fleets_by_user: dict[int, set[int]] = {}
    if metric in KILL_BOARD_FILTERS:
        mails_by_user = kill_mails_by_user(
            campaign, first_day, **KILL_BOARD_FILTERS[metric]
        )
        by_user = {user_id: 0 for user_id in mails_by_user}
    elif metric == "fleets":
        fleets_by_user = fleets.fleet_ids_by_user(
            campaign, day_bounds(first_day)[0] if first_day else None
        )
        by_user = {user_id: 0 for user_id in fleets_by_user}
    else:
        by_user = dict(
            queryset.values("user_id")
            .annotate(value=Sum(field))
            .filter(value__gt=0)
            .values_list("user_id", "value")
        )
    corporation_by_user = dict(
        EvePlayer.objects.filter(
            user_id__in=list(by_user), primary_character__isnull=False
        ).values_list("user_id", "primary_character__corporation_id")
    )
    names = dict(
        EveCorporation.objects.filter(
            corporation_id__in=set(corporation_by_user.values()) - {None}
        ).values_list("corporation_id", "name")
    )

    corporations: dict[int | None, dict] = {}
    mails_by_corporation: dict[int | None, dict[int, int]] = {}
    fleets_by_corporation: dict[int | None, set[int]] = {}
    for user_id, value in by_user.items():
        corporation_id = corporation_by_user.get(user_id)
        row = corporations.setdefault(
            corporation_id,
            {
                "corporation_id": corporation_id,
                "corporation_name": names.get(corporation_id, ""),
                "pilots": 0,
                "value": 0.0,
            },
        )
        row["pilots"] += 1
        row["value"] += float(value)
        mails_by_corporation.setdefault(corporation_id, {}).update(
            mails_by_user.get(user_id, {})
        )
        fleets_by_corporation.setdefault(corporation_id, set()).update(
            fleets_by_user.get(user_id, ())
        )

    if metric in KILL_BOARD_FILTERS:
        for corporation_id, row in corporations.items():
            mails = mails_by_corporation[corporation_id]
            row["value"] = float(
                sum(mails.values()) if metric == "isk" else len(mails)
            )
    elif metric == "fleets":
        for corporation_id, row in corporations.items():
            row["value"] = float(len(fleets_by_corporation[corporation_id]))

    rows = sorted(
        corporations.values(),
        key=lambda row: (
            -row["value"],
            row["corporation_id"] is None,
            row["corporation_name"].lower(),
        ),
    )[:limit]
    return [{"rank": index, **row} for index, row in enumerate(rows, start=1)]


# The boards that read mails rather than day rows when pilots are pooled,
# and the mail filter each one applies.
KILL_BOARD_FILTERS = {
    "kills": {},
    "isk": {},
    "structures": {"killmail__is_structure": True},
    "capitals": {"killmail__is_capital": True},
}


def _period_first_day(period: str) -> date | None:
    """The first campaign day a board period covers; None for all of it."""
    if period == "week":
        return campaign_week_start()
    if period == "rolling7":
        return campaign_day() - timedelta(days=7)
    return None


def _kills_in_period(campaign, first_day: date | None):
    """``(user_id, killmail_id, isk_value)`` for every scored kill.

    The same mails ``_add_killmails`` counts as kills, one row per
    character, so callers pooling pilots dedupe on the mail id.
    """
    participants = CampaignKillmailParticipant.objects.filter(
        killmail__campaign=campaign,
        killmail__outcome=KillmailOutcome.KILL,
        killmail__is_pod=False,
        enlisted=True,
        user__isnull=False,
        role="attacker",
    )
    if first_day:
        participants = participants.filter(
            killmail__killmail_time__gte=day_bounds(first_day)[0]
        )
    return participants.values_list(
        "user_id", "killmail_id", "killmail__isk_value"
    )


def kill_mails_by_user(
    campaign, first_day: date | None = None, **mail_filters
) -> dict[int, dict[int, int]]:
    """``{user_id: {killmail_id: isk_value}}`` for every scored kill.

    Anything that pools pilots (a corporation, the whole roster) merges
    these dicts, so a mail several of them were on counts once.
    """
    mails: dict[int, dict[int, int]] = {}
    for user_id, mail_id, isk_value in _kills_in_period(
        campaign, first_day
    ).filter(**mail_filters):
        mails.setdefault(user_id, {})[mail_id] = isk_value
    return mails


def primary_characters(user_ids) -> dict[int, tuple[int, str]]:
    """``{user_id: (character_id, character_name)}`` for each pilot's main.

    A board shows the pilot's face and in-game name, not their web login.
    A pilot without a primary character falls back to the username in the
    caller, so they are simply absent here.
    """
    return primary_refs_for_users(user_ids)


def campaign_totals(campaign: Campaign) -> dict:
    """The stat bar under the hero."""
    mails = CampaignKillmail.objects.filter(campaign=campaign)
    kills = mails.filter(outcome=KillmailOutcome.KILL)
    losses = mails.filter(outcome=KillmailOutcome.LOSS)
    sites = CampaignSiteCompletion.objects.filter(campaign=campaign)
    scored_sites = sites.filter(scored=True)

    # Advantage is a sum over a handful of site kinds, so count the kinds
    # rather than walking every completion ever recorded.
    advantage = 0.0
    for site_kind, count in (
        scored_sites.values_list("site_kind")
        .annotate(n=Count("id"))
        .values_list("site_kind", "n")
    ):
        advantage += (
            ADVANTAGE_DELTA_BY_SITE_KIND.get(site_kind, (0.0, 0.0))[0] * count
        )

    return {
        "enlisted": campaign.enlistments.filter(status="active").count(),
        "kills": kills.count(),
        "losses": losses.count(),
        "isk_destroyed": kills.aggregate(v=Sum("isk_value"))["v"] or 0,
        "isk_lost": losses.aggregate(v=Sum("isk_value"))["v"] or 0,
        "complexes": scored_sites.filter(site_kind=SiteKind.COMPLEX).count(),
        "advantage_sites": scored_sites.exclude(
            site_kind=SiteKind.COMPLEX
        ).count(),
        "advantage_generated": round(advantage, 1),
        "structure_kills": kills.filter(is_structure=True).count(),
        "capital_kills": kills.filter(is_capital=True).count(),
        "structures_destroyed": campaign.structures.filter(
            status="destroyed"
        ).count(),
        "structures_remaining": campaign.structures.exclude(
            status="destroyed"
        ).count(),
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
        "kills": week_kills(campaign),
        "complexes": rows.aggregate(v=Sum("complexes"))["v"] or 0,
        "active_pilots": rows.filter(active=True)
        .values("user_id")
        .distinct()
        .count(),
    }


def week_kills(campaign: Campaign) -> int:
    """Kills this campaign week, each mail once however many of us were on it."""
    return (
        _kills_in_period(campaign, campaign_week_start())
        .values("killmail_id")
        .distinct()
        .count()
    )
