"""Minmatar Fleet Academy graduation pipeline.

Every Academy main is placed by how long they have been in L3ARN, from their
corporation history. After REVIEW_AFTER_DAYS they are due for a review, where
Academy leadership graduates them to an alliance corporation, keeps them, or
releases them (applications.models.AcademyGraduationReview).

The graduation bar and the corp routing follow the academy-graduation agent
skill (.claude/skills/academy-graduation/SKILL.md). Activity counts every
character the person has, over the last WINDOW_DAYS.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from django.contrib.auth.models import User
from django.db.models import Count, Max, Sum
from django.utils import timezone

from app.cache import CachedRollup
from applications.models import AcademyGraduationReview
from discord.models import DiscordChannelActivityRecord
from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.killmail_classes import SMALL_GANG_MAX_ATTACKERS
from eveonline.models import (
    EveCharacter,
    EveCharacterCorporationHistory,
    EveCharacterKillmailAttacker,
    EveCharacterSkill,
    EveCorporation,
    EvePlayer,
)
from fleets.models import EveFleetInstanceMember

REVIEW_AFTER_DAYS = 180
WINDOW_DAYS = 90
RECENT_DAYS = 30
GRADUATED_WINDOW_DAYS = 90
# Attackers on the mail: small up to SMALL_GANG_MAX_ATTACKERS, large from here.
LARGE_GANG_MIN_ATTACKERS = 25
METRICS_CACHE_SECONDS = 600

# The graduation bar: past REVIEW_AFTER_DAYS and any one of these.
BAR_FLEETS = 4
BAR_KILLS = 8
BAR_VOICE_HOURS = 10
BAR_VOICE_KILLS = 3
BAR_VETERAN_SKILL_POINTS = 80_000_000
BAR_VETERAN_KILLS = 1

# Routing (academy-graduation skill).
TDT_MIN_SKILL_POINTS = 30_000_000
TDT_MIN_KILLS_30D = 10
TDT_MIN_KILLS_90D = 30
SLTAR_MIN_FLEETS = 8
BUILDING_MAX_SKILL_POINTS = 30_000_000
EU_PRIME_TIMES = ("EU", "AP_EU")
MAX_SUGGESTIONS = 2

STAGE_TRAINING = "training"
STAGE_DUE = "due"
STAGE_KEPT = "kept"
STAGE_GRADUATING = "graduating"
STAGE_RELEASED = "released"

REASON_EU_SKIRMISH = "eu_skirmish"
REASON_KILLBOARD = "killboard"
REASON_LARGE_GANG = "large_gang"
REASON_FLEET_REGULAR = "fleet_regular"
REASON_BUILDING = "building"
REASON_ALL_TIMEZONES = "all_timezones"


@dataclass
class PilotActivity:
    """One person's last WINDOW_DAYS, keyed to their Academy main."""

    user_id: int
    username: str
    character_id: int
    character_name: str
    prime_time: Optional[str]
    joined_at: Optional[datetime]
    join_estimated: bool
    skill_points: Optional[int]
    fleets_90d: int = 0
    fleets_30d: int = 0
    kills_90d: int = 0
    kills_30d: int = 0
    small_gang_kills: int = 0
    medium_gang_kills: int = 0
    large_gang_kills: int = 0
    voice_hours_90d: int = 0


@dataclass
class Pilot:
    activity: PilotActivity
    days_in_academy: int
    ready: bool
    inactive: bool
    stage: str
    suggestions: list[tuple[str, str]] = field(default_factory=list)
    last_review: Optional[AcademyGraduationReview] = None


def is_academy(corporation: Optional[EveCorporation]) -> bool:
    # Imported here: applications.l3arn imports eveonline helpers lazily too.
    from applications.l3arn import (  # pylint: disable=import-outside-toplevel
        is_l3arn_corporation,
    )

    return is_l3arn_corporation(corporation)


def meets_bar(activity: PilotActivity, days: int) -> bool:
    if days < REVIEW_AFTER_DAYS:
        return False
    kills = activity.kills_90d
    return (
        activity.fleets_90d >= BAR_FLEETS
        or kills >= BAR_KILLS
        or (
            activity.voice_hours_90d >= BAR_VOICE_HOURS
            and kills >= BAR_VOICE_KILLS
        )
        or (
            (activity.skill_points or 0) >= BAR_VETERAN_SKILL_POINTS
            and kills >= BAR_VETERAN_KILLS
        )
    )


def suggest_corporations(activity: PilotActivity) -> list[tuple[str, str]]:
    """(ticker, reason) pairs, best first, for a pilot who meets the bar."""
    prime_time = (activity.prime_time or "").upper()
    skill_points = activity.skill_points or 0
    kills = activity.kills_90d
    large = activity.large_gang_kills
    skirmish = activity.small_gang_kills + activity.medium_gang_kills
    eu = prime_time in EU_PRIME_TIMES
    picks: list[tuple[str, str]] = []
    if eu:
        picks.append(("FOSFO", REASON_EU_SKIRMISH))
    if (
        not eu
        and skill_points >= TDT_MIN_SKILL_POINTS
        and activity.kills_30d >= TDT_MIN_KILLS_30D
        and kills >= TDT_MIN_KILLS_90D
        and skirmish > large
    ):
        picks.append(("TDT", REASON_KILLBOARD))
    if kills and large * 2 >= kills:
        picks.append(("A-RAT", REASON_LARGE_GANG))
    if activity.fleets_90d >= SLTAR_MIN_FLEETS:
        picks.append(("SLTAR", REASON_FLEET_REGULAR))
    elif skill_points < BUILDING_MAX_SKILL_POINTS or activity.kills_30d == 0:
        picks.append(("SLTAR", REASON_BUILDING))
    if not picks:
        picks.append(("A-RAT", REASON_ALL_TIMEZONES))
    seen: set[str] = set()
    unique = []
    for ticker, reason in picks:
        if ticker not in seen:
            seen.add(ticker)
            unique.append((ticker, reason))
    return unique[:MAX_SUGGESTIONS]


def graduate_corporations() -> list[EveCorporation]:
    """Alliance corporations a pilot can graduate to (the Academy excluded)."""
    return [
        corporation
        for corporation in EveCorporation.objects.filter(
            alliance__alliance_id=MINMATAR_FLEET_ALLIANCE_ID
        ).order_by("name")
        if corporation.ticker and not is_academy(corporation)
    ]


def _academy_players(corporation: EveCorporation) -> list[EvePlayer]:
    return list(
        EvePlayer.objects.filter(
            primary_character__corporation_id=corporation.corporation_id,
            user__isnull=False,
        ).select_related("primary_character", "user")
    )


def _join_dates(corporation: EveCorporation, mains: list[EveCharacter]):
    """The start of each main's latest stint in the Academy."""
    return dict(
        EveCharacterCorporationHistory.objects.filter(
            character__in=mains, corporation_id=corporation.corporation_id
        )
        .values("character_id")
        .annotate(joined=Max("start_date"))
        .values_list("character_id", "joined")
    )


def _skill_points(mains: list[EveCharacter]) -> dict[int, int]:
    return dict(
        EveCharacterSkill.objects.filter(character__in=mains)
        .values("character_id")
        .annotate(total=Sum("skill_points"))
        .values_list("character_id", "total")
    )


def _chunks(items: list, size: int = 2000):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def collect_activity(corporation: EveCorporation) -> list[PilotActivity]:
    """Activity for every Academy main's person, from a handful of queries."""
    now = timezone.now()
    since = now - timedelta(days=WINDOW_DAYS)
    since_recent = now - timedelta(days=RECENT_DAYS)
    players = _academy_players(corporation)
    mains = [player.primary_character for player in players]
    joined = _join_dates(corporation, mains)
    skill_points = _skill_points(mains)

    owner: dict[int, int] = {}
    for user_id, character_id in EveCharacter.objects.filter(
        user_id__in=[player.user_id for player in players]
    ).values_list("user_id", "character_id"):
        owner[character_id] = user_id
    characters_of: dict[int, set[int]] = defaultdict(set)
    for character_id, user_id in owner.items():
        characters_of[user_id].add(character_id)

    fleets: dict[int, set] = defaultdict(set)
    fleets_recent: dict[int, set] = defaultdict(set)
    for (
        character_id,
        instance_id,
        join_time,
    ) in EveFleetInstanceMember.objects.filter(
        character_id__in=list(owner), join_time__gte=since
    ).values_list(
        "character_id", "eve_fleet_instance_id", "join_time"
    ):
        user_id = owner[character_id]
        fleets[user_id].add(instance_id)
        if join_time >= since_recent:
            fleets_recent[user_id].add(instance_id)

    kills: dict[int, dict] = defaultdict(dict)
    for row in EveCharacterKillmailAttacker.objects.filter(
        character_id__in=list(owner), killmail__killmail_time__gte=since
    ).values_list(
        "character_id",
        "killmail_id",
        "killmail__killmail_time",
        "killmail__victim_character_id",
    ):
        character_id, killmail_id, killed_at, victim_id = row
        user_id = owner[character_id]
        if victim_id in characters_of[user_id]:
            continue
        kills[user_id][killmail_id] = killed_at
    attackers: dict[int, int] = {}
    killmail_ids = list({k for mails in kills.values() for k in mails})
    for chunk in _chunks(killmail_ids):
        attackers.update(
            EveCharacterKillmailAttacker.objects.filter(killmail_id__in=chunk)
            .values("killmail_id")
            .annotate(n=Count("id"))
            .values_list("killmail_id", "n")
        )

    voice = dict(
        DiscordChannelActivityRecord.objects.filter(
            username__in=[player.user.username for player in players],
            activity_type="voice_minute",
            created_on__gte=since,
        )
        .values("username")
        .annotate(minutes=Sum("quantity"))
        .values_list("username", "minutes")
    )

    activities = []
    for player in players:
        main = player.primary_character
        user_id = player.user_id
        joined_at = joined.get(main.id)
        mails = kills.get(user_id, {})
        sizes = [attackers.get(killmail_id, 1) for killmail_id in mails]
        activities.append(
            PilotActivity(
                user_id=user_id,
                username=player.user.username,
                character_id=main.character_id,
                character_name=main.character_name,
                prime_time=player.prime_time or None,
                joined_at=joined_at or main.created_at,
                join_estimated=joined_at is None,
                skill_points=skill_points.get(main.id),
                fleets_90d=len(fleets.get(user_id, ())),
                fleets_30d=len(fleets_recent.get(user_id, ())),
                kills_90d=len(mails),
                kills_30d=sum(
                    1
                    for killed_at in mails.values()
                    if killed_at >= since_recent
                ),
                small_gang_kills=sum(
                    1 for n in sizes if n <= SMALL_GANG_MAX_ATTACKERS
                ),
                medium_gang_kills=sum(
                    1
                    for n in sizes
                    if SMALL_GANG_MAX_ATTACKERS < n < LARGE_GANG_MIN_ATTACKERS
                ),
                large_gang_kills=sum(
                    1 for n in sizes if n >= LARGE_GANG_MIN_ATTACKERS
                ),
                voice_hours_90d=round(
                    (voice.get(player.user.username) or 0) / 60
                ),
            )
        )
    return activities


# A bounded scan (the Academy's members, 90 days), light enough for a request;
# reviews are read live on top of it.
ACTIVITY = CachedRollup(
    key="academy_graduation_activity:v1:{corporation_id}",
    ttl=METRICS_CACHE_SECONDS,
    lock_key="academy_graduation_activity:computing:{corporation_id}",
    lock_ttl=120,
)


def cached_activity(corporation: EveCorporation) -> list[PilotActivity]:
    return ACTIVITY.get_or_compute(
        lambda: collect_activity(corporation),
        corporation_id=corporation.corporation_id,
    )


def latest_reviews(user_ids) -> dict[int, AcademyGraduationReview]:
    latest: dict[int, AcademyGraduationReview] = {}
    for review in AcademyGraduationReview.objects.filter(
        user_id__in=list(user_ids)
    ).select_related("reviewed_by"):
        latest.setdefault(review.user_id, review)
    return latest


def _stage(days: int, review: Optional[AcademyGraduationReview]) -> str:
    if review is not None:
        if review.decision == AcademyGraduationReview.DECISION_KEEP:
            return STAGE_KEPT
        if review.decision == AcademyGraduationReview.DECISION_GRADUATE:
            return STAGE_GRADUATING
        return STAGE_RELEASED
    return STAGE_DUE if days >= REVIEW_AFTER_DAYS else STAGE_TRAINING


def pipeline_pilots(corporation: EveCorporation) -> list[Pilot]:
    """Every Academy main, ordered as the review queue: due pilots who meet
    the bar first, then the longest waiting; everyone else after."""
    now = timezone.now()
    activities = cached_activity(corporation)
    reviews = latest_reviews(activity.user_id for activity in activities)
    pilots = []
    for activity in activities:
        days = (
            max(0, (now - activity.joined_at).days)
            if activity.joined_at
            else 0
        )
        ready = meets_bar(activity, days)
        pilots.append(
            Pilot(
                activity=activity,
                days_in_academy=days,
                ready=ready,
                inactive=activity.fleets_30d == 0 and activity.kills_30d == 0,
                stage=_stage(days, reviews.get(activity.user_id)),
                suggestions=suggest_corporations(activity) if ready else [],
                last_review=reviews.get(activity.user_id),
            )
        )
    pilots.sort(
        key=lambda pilot: (
            pilot.stage != STAGE_DUE,
            not pilot.ready,
            -pilot.days_in_academy,
        )
    )
    return pilots


def recent_graduates(corporation: EveCorporation) -> list[dict]:
    """Mains who left the Academy for an alliance corporation lately."""
    cutoff = timezone.now() - timedelta(days=GRADUATED_WINDOW_DAYS)
    corporations = {
        corporation.corporation_id: corporation
        for corporation in graduate_corporations()
    }
    moves = list(
        EveCharacterCorporationHistory.objects.filter(
            start_date__gte=cutoff,
            corporation_id__in=list(corporations),
            character__eveplayer__isnull=False,
        )
        .select_related("character")
        .order_by("-start_date")
    )
    academy_starts: dict[int, list] = defaultdict(list)
    for character_id, start in EveCharacterCorporationHistory.objects.filter(
        character_id__in={move.character_id for move in moves},
        corporation_id=corporation.corporation_id,
    ).values_list("character_id", "start_date"):
        academy_starts[character_id].append(start)
    graduates = []
    seen: set[int] = set()
    for move in moves:
        before = [
            start
            for start in academy_starts.get(move.character_id, [])
            if start < move.start_date
        ]
        if not before or move.character_id in seen:
            continue
        seen.add(move.character_id)
        target = corporations[move.corporation_id]
        graduates.append(
            {
                "character_id": move.character.character_id,
                "character_name": move.character.character_name,
                "corporation_id": target.corporation_id,
                "ticker": target.ticker,
                "graduated_at": move.start_date,
                "days_in_academy": (move.start_date - max(before)).days,
            }
        )
    return graduates


def record_review(
    corporation: EveCorporation,
    reviewer: User,
    character_id: int,
    decision: str,
    corporation_ids: list[int],
    note: str,
) -> AcademyGraduationReview | str:
    """Save a decision; returns the review, or an error message."""
    player = (
        EvePlayer.objects.filter(
            primary_character__character_id=character_id,
            primary_character__corporation_id=corporation.corporation_id,
            user__isnull=False,
        )
        .select_related("user")
        .first()
    )
    if player is None:
        return "That pilot isn't an Academy main"
    valid = dict(AcademyGraduationReview.DECISION_CHOICES)
    if decision not in valid:
        return "Unknown decision"
    routed: list[int] = []
    if decision == AcademyGraduationReview.DECISION_GRADUATE:
        allowed = {c.corporation_id for c in graduate_corporations()}
        routed = [
            cid for cid in dict.fromkeys(corporation_ids) if cid in allowed
        ]
        if not routed:
            return "Pick a corporation to graduate to"
    return AcademyGraduationReview.objects.create(
        user=player.user,
        character_id=character_id,
        decision=decision,
        corporation_ids=routed,
        note=(note or "").strip()[:1000],
        reviewed_by=reviewer,
    )
