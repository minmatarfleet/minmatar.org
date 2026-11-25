"""Character ESI sync: what each section is, how often it refreshes, and how
one character's due sections are run and stamped.

The scheduler and the tasks live in ``eveonline.tasks.character_sync``;
this module has no Celery entry points so the tribes refresh button and the
legacy ``update_character`` task can run sections inline.

See docs/architecture/character-sync.md.
"""

from __future__ import annotations

import logging
import math
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Iterable

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from esi.exceptions import ESIErrorLimitException
from esi.models import Token

from app.celery import app
from app.locks import single_flight
from eveonline import esi_budget
from eveonline.client import record_esi_outcomes
from eveonline.helpers.alliances import tracked_alliance_ids
from eveonline.helpers.characters import (
    update_character_assets as refresh_character_assets,
    update_character_blueprints as refresh_character_blueprints,
    update_character_clones as refresh_character_clones,
    update_character_contracts as refresh_character_contracts,
    update_character_industry_jobs as refresh_character_industry_jobs,
    update_character_killmails as refresh_character_killmails,
    update_character_mining as refresh_character_mining,
    update_character_planets as refresh_character_planets,
    update_character_skills as refresh_character_skills,
)
from eveonline.models import (
    EveCharacter,
    EveCharacterMiningDelta,
    EveCharacterMiningEntry,
    EveCharacterSkill,
    EveCharacterSyncState,
)
from eveonline.utils import get_esi_downtime_countdown

logger = logging.getLogger(__name__)

# Modes (settings.CHARACTER_SYNC_MODE)
MODE_FANOUT = "fanout"
MODE_SHADOW = "shadow"
MODE_SCHEDULED = "scheduled"
MODES = (MODE_FANOUT, MODE_SHADOW, MODE_SCHEDULED)

SCOPE_ASSETS = ["esi-assets.read_assets.v1"]
SCOPE_SKILLS = ["esi-skills.read_skills.v1"]
SCOPE_KILLMAILS = ["esi-killmails.read_killmails.v1"]
SCOPE_CONTRACTS = ["esi-contracts.read_character_contracts.v1"]
SCOPE_INDUSTRY_JOBS = ["esi-industry.read_character_jobs.v1"]
SCOPE_MINING = ["esi-industry.read_character_mining.v1"]
SCOPE_PLANETS = ["esi-planets.manage_planets.v1"]
SCOPE_BLUEPRINTS = ["esi-characters.read_blueprints.v1"]
SCOPE_CLONES = ["esi-clones.read_clones.v1"]
SCOPE_IMPLANTS = ["esi-clones.read_implants.v1"]

# Audience intervals. Which one applies, highest priority first: active
# fleet, industry, on leave, then the section's own interval.
FLEET_INTERVAL = timedelta(minutes=15)
# Pilots stay in the fleet audience this long after the fleet ends, to
# catch late killmails and ledger entries.
FLEET_TAIL = timedelta(minutes=30)
# A fleet instance with no end time older than this is treated as stale.
FLEET_MAX_AGE = timedelta(hours=12)
INDUSTRY_INTERVAL = timedelta(hours=1)
ON_LEAVE_INTERVAL = timedelta(hours=72)
PI_PLANETS_INTERVAL = timedelta(hours=72)
PI_TRIBE_GROUP_CODES = (
    "supply.planetary-interaction",
    "industry.planetary-interaction",
)

# Mining ledger tiers: how likely a pilot is to have new ledger rows soon.
# A pull that finds new ore makes the pilot hot at once; a hot pilot cools
# off once no pull has found any for MINING_HOT_WINDOW. ESI caches the ledger
# for about ten minutes, so pulling a hot pilot faster gains nothing.
MINING_HOT_INTERVAL = timedelta(minutes=10)
MINING_HOT_WINDOW = timedelta(minutes=25)
MINING_WARM_INTERVAL = timedelta(hours=1)
MINING_WARM_DAYS = 1  # ledger rows today or yesterday (UTC)
MINING_COOL_INTERVAL = timedelta(hours=6)
MINING_COOL_DAYS = 30
MINING_UNLIKELY_INTERVAL = timedelta(hours=72)
# Mining Frigate, Expedition Frigates, Mining Barge, Exhumers, Ice Harvesting:
# every pilot who mined in the last 30 days has one of these.
MINING_SHIP_SKILL_IDS = (32918, 33856, 17940, 22551, 16281)
MINING_SKILLS_CACHE_KEY = "character_sync:mining_skills:v1"
MINING_SKILLS_CACHE_SECONDS = 60 * 60

# Failure handling
FAILURE_RETRY = timedelta(minutes=30)
TRANSIENT_RETRY = timedelta(minutes=15)
QUICK_RETRIES = 3
JITTER = 0.1
# A queued row is not picked again for this long, so a character waiting in
# the queue is not queued twice.
QUEUED_LEASE = timedelta(minutes=15)
# How long one character's sync may hold its lock.
SYNC_LOCK_SECONDS = 15 * 60
# Characters added this recently with nothing synced are retried whatever
# their scope, so a first fetch lost to downtime is not lost for good.
NEW_CHARACTER_WINDOW = timedelta(days=7)


def sync_mode() -> str:
    mode = getattr(settings, "CHARACTER_SYNC_MODE", MODE_FANOUT)
    if mode not in MODES:
        logger.warning(
            "Unknown CHARACTER_SYNC_MODE %r; using %s", mode, MODE_FANOUT
        )
        return MODE_FANOUT
    return mode


# Section functions. Each takes the character and returns nothing; the
# outcome comes from the ESI responses recorded while it runs.


def _run_assets(character: EveCharacter) -> None:
    refresh_character_assets(character.character_id)


def _run_skills(character: EveCharacter) -> None:
    """Sync skills; re-rate the character only when a level changed."""
    changed = refresh_character_skills(character.character_id)
    if changed and character.user_id:
        app.signature(
            "capabilities.tasks.refresh_character_readiness",
            args=[character.pk],
        ).delay()


def _run_killmails(character: EveCharacter) -> None:
    refresh_character_killmails(character.character_id)


def _owns_open_industry_order(character: EveCharacter) -> bool:
    # pylint: disable=import-outside-toplevel
    from industry.models import IndustryOrder

    return IndustryOrder.objects.filter(
        character=character, fulfilled_at__isnull=True
    ).exists()


def _run_contracts(character: EveCharacter) -> None:
    refresh_character_contracts(character.character_id)
    # Reconcile only reads the order owner's contracts, so only an owner of
    # an open order has anything to reconcile.
    if _owns_open_industry_order(character):
        # A signature, not send_task, so AppTask dedupes it like any call.
        app.signature(
            "industry.tasks.reconcile_industry_contract_associations_for_character_task",
            args=[character.character_id],
        ).delay()


def _run_industry_jobs(character: EveCharacter) -> None:
    result = refresh_character_industry_jobs(character.character_id)
    created_job_ids = result[1] if isinstance(result, tuple) else []
    if created_job_ids:
        app.signature(
            "industry.tasks.emit_order_job_notifications_for_jobs",
            args=[created_job_ids],
        ).delay()


def _run_mining(character: EveCharacter) -> None:
    refresh_character_mining(character.character_id)


def _run_planets(character: EveCharacter) -> None:
    refresh_character_planets(character.character_id)


def _run_blueprints(character: EveCharacter) -> None:
    refresh_character_blueprints(character.character_id)


def _run_clones(character: EveCharacter) -> None:
    refresh_character_clones(character.character_id)


@dataclass(frozen=True)
class Section:
    name: str
    # Every scope list must be granted (each is checked with Token.get_token).
    scopes: tuple[tuple[str, ...], ...]
    run: Callable[[EveCharacter], None]
    interval: timedelta
    # Rough relative ESI cost, for the scheduler's per-tick budget. Assets
    # and blueprints are paged.
    weight: int = 1


ASSETS = "assets"
SKILLS = "skills"
KILLMAILS = "killmails"
CONTRACTS = "contracts"
INDUSTRY_JOBS = "industry_jobs"
MINING = "mining"
PLANETS = "planets"
BLUEPRINTS = "blueprints"
CLONES = "clones"

# Today's order in update_character.
SECTIONS: tuple[Section, ...] = (
    Section(
        ASSETS, (tuple(SCOPE_ASSETS),), _run_assets, timedelta(hours=4), 3
    ),
    Section(SKILLS, (tuple(SCOPE_SKILLS),), _run_skills, timedelta(hours=24)),
    Section(
        KILLMAILS,
        (tuple(SCOPE_KILLMAILS),),
        _run_killmails,
        timedelta(hours=24),
        2,
    ),
    Section(
        CONTRACTS,
        (tuple(SCOPE_CONTRACTS),),
        _run_contracts,
        timedelta(hours=4),
    ),
    Section(
        INDUSTRY_JOBS,
        (tuple(SCOPE_INDUSTRY_JOBS),),
        _run_industry_jobs,
        timedelta(hours=4),
    ),
    Section(MINING, (tuple(SCOPE_MINING),), _run_mining, timedelta(hours=24)),
    Section(
        PLANETS, (tuple(SCOPE_PLANETS),), _run_planets, timedelta(days=7), 2
    ),
    Section(
        BLUEPRINTS,
        (tuple(SCOPE_BLUEPRINTS),),
        _run_blueprints,
        timedelta(hours=24),
        3,
    ),
    Section(
        CLONES,
        (tuple(SCOPE_CLONES), tuple(SCOPE_IMPLANTS)),
        _run_clones,
        timedelta(hours=24),
    ),
)
SECTIONS_BY_NAME = {section.name: section for section in SECTIONS}


# Audiences


@dataclass
class Audiences:
    """Character pks in each audience that changes a section's interval."""

    members: set[int] = field(default_factory=set)
    fleet: set[int] = field(default_factory=set)
    contract_owners: set[int] = field(default_factory=set)
    job_assignees: set[int] = field(default_factory=set)
    on_leave: set[int] = field(default_factory=set)
    pi: set[int] = field(default_factory=set)
    # Mining ledger tiers (see MINING_* above).
    mining_hot: set[int] = field(default_factory=set)
    mining_warm: set[int] = field(default_factory=set)
    mining_cool: set[int] = field(default_factory=set)
    # Skills synced but no mining-ship skill: unlikely to mine soon.
    mining_unlikely: set[int] = field(default_factory=set)

    def eligible(self) -> set[int]:
        """Every character pk the scheduler keeps fresh."""
        return self.members | self.contract_owners | self.job_assignees

    def in_scope(self, section: str, pk: int) -> bool:
        if pk in self.members:
            return True
        if section == CONTRACTS:
            return pk in self.contract_owners
        if section == INDUSTRY_JOBS:
            return pk in self.job_assignees
        return False

    def interval(self, section: Section, pk: int) -> timedelta:
        name = section.name
        if name == MINING:
            return self.mining_interval(pk)
        if name == KILLMAILS and pk in self.fleet:
            return FLEET_INTERVAL
        if name == CONTRACTS and pk in self.contract_owners:
            return INDUSTRY_INTERVAL
        if name == INDUSTRY_JOBS and pk in self.job_assignees:
            return INDUSTRY_INTERVAL
        base = section.interval
        if name == PLANETS and pk in self.pi:
            base = PI_PLANETS_INTERVAL
        if pk in self.on_leave:
            return max(base, ON_LEAVE_INTERVAL)
        return base

    def mining_interval(self, pk: int) -> timedelta:
        if pk in self.mining_hot:
            return MINING_HOT_INTERVAL
        if pk in self.fleet:
            return FLEET_INTERVAL
        if pk in self.mining_warm:
            return MINING_WARM_INTERVAL
        if pk in self.mining_cool:
            return MINING_COOL_INTERVAL
        base = SECTIONS_BY_NAME[MINING].interval
        if pk in self.mining_unlikely:
            base = MINING_UNLIKELY_INTERVAL
        if pk in self.on_leave:
            return max(base, ON_LEAVE_INTERVAL)
        return base


def mined_recently(character_pk: int, since: datetime) -> bool:
    """Whether a ledger pull since ``since`` found new ore."""
    return EveCharacterMiningDelta.objects.filter(
        character_id=character_pk, observed_at__gte=since
    ).exists()


def _mining_tiers(now, pks: set[int] | None) -> dict[str, set[int]]:
    today = now.date()
    hot = EveCharacterMiningDelta.objects.filter(
        observed_at__gte=now - MINING_HOT_WINDOW
    ).values_list("character_id", flat=True)
    warm = EveCharacterMiningEntry.objects.filter(
        date__gte=today - timedelta(days=MINING_WARM_DAYS)
    ).values_list("character_id", flat=True)
    cool = EveCharacterMiningEntry.objects.filter(
        date__gte=today - timedelta(days=MINING_COOL_DAYS)
    ).values_list("character_id", flat=True)
    if pks is not None:
        hot, warm, cool = (
            q.filter(character_id__in=pks) for q in (hot, warm, cool)
        )
    tiers = {
        "mining_hot": set(hot),
        "mining_warm": set(warm),
        "mining_cool": set(cool),
    }
    with_skills, able = _mining_skill_sets()
    unlikely = with_skills - able
    tiers["mining_unlikely"] = unlikely if pks is None else unlikely & pks
    return tiers


def _mining_skill_sets() -> tuple[set[int], set[int]]:
    """Character pks with any skills synced, and those with a mining-ship
    skill. Skills change slowly and the table is large, so this is cached."""
    cached = cache.get(MINING_SKILLS_CACHE_KEY)
    if cached is not None:
        return set(cached[0]), set(cached[1])
    with_skills = set(
        EveCharacterSkill.objects.values_list(
            "character_id", flat=True
        ).distinct()
    )
    able = set(
        EveCharacterSkill.objects.filter(
            skill_id__in=MINING_SHIP_SKILL_IDS, skill_level__gte=1
        )
        .values_list("character_id", flat=True)
        .distinct()
    )
    cache.set(
        MINING_SKILLS_CACHE_KEY,
        (sorted(with_skills), sorted(able)),
        MINING_SKILLS_CACHE_SECONDS,
    )
    return with_skills, able


def _character_pks(queryset, pks: set[int] | None) -> set[int]:
    if pks is not None:
        queryset = queryset.filter(pk__in=pks)
    return set(queryset.values_list("pk", flat=True))


def _characters_of_users(user_ids, pks: set[int] | None) -> set[int]:
    return _character_pks(
        EveCharacter.objects.filter(user_id__in=list(user_ids)), pks
    )


def load_audiences(character_pks: Iterable[int] | None = None) -> Audiences:
    """Work out each audience, for every character or only ``character_pks``."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstanceMember
    from groups.models import UserCommunityStatus
    from industry.models import IndustryOrder, IndustryOrderItemAssignment
    from tribes.models import TribeGroupMembership

    pks = set(character_pks) if character_pks is not None else None
    now = timezone.now()

    member_users = User.objects.filter(
        evecharacter__alliance_id__in=tracked_alliance_ids()
    ).values("pk")
    members = _character_pks(
        EveCharacter.objects.filter(
            user__in=member_users, esi_deleted=False
        ).exclude(token=None),
        pks,
    )

    fleet_character_ids = EveFleetInstanceMember.objects.filter(
        Q(
            eve_fleet_instance__end_time__isnull=True,
            eve_fleet_instance__start_time__gte=now - FLEET_MAX_AGE,
        )
        | Q(eve_fleet_instance__end_time__gte=now - FLEET_TAIL)
    ).values("character_id")
    fleet = _character_pks(
        EveCharacter.objects.filter(character_id__in=fleet_character_ids), pks
    )

    contract_owners = _character_pks(
        EveCharacter.objects.filter(
            pk__in=IndustryOrder.objects.filter(
                fulfilled_at__isnull=True, character__isnull=False
            ).values("character_id")
        ),
        pks,
    )

    assigned = IndustryOrderItemAssignment.objects.filter(
        order_item__order__fulfilled_at__isnull=True,
        delivered_at__isnull=True,
    )
    assigned_pks = set(assigned.values_list("character_id", flat=True))
    assignee_users = set(
        EveCharacter.objects.filter(
            pk__in=assigned_pks, user__isnull=False
        ).values_list("user_id", flat=True)
    )
    job_assignees = _characters_of_users(assignee_users, pks) | (
        assigned_pks if pks is None else assigned_pks & pks
    )

    on_leave = _characters_of_users(
        UserCommunityStatus.objects.filter(
            status__in=UserCommunityStatus.AWAY_STATUSES
        ).values_list("user_id", flat=True),
        pks,
    )
    pi = _characters_of_users(
        TribeGroupMembership.objects.filter(
            status=TribeGroupMembership.STATUS_ACTIVE,
            tribe_group__code__in=PI_TRIBE_GROUP_CODES,
        ).values_list("user_id", flat=True),
        pks,
    )
    return Audiences(
        members=members,
        fleet=fleet,
        contract_owners=contract_owners,
        job_assignees=job_assignees,
        on_leave=on_leave,
        pi=pi,
        **_mining_tiers(now, pks),
    )


# Outcomes


class Outcome(str, Enum):
    OK = "ok"
    NO_SCOPE = "no_scope"
    SUSPENDED = "suspended"
    # A 4xx for this character: broken token, forbidden.
    FAILED = "failed"
    # 5xx, a request that never completed, or an exception.
    TRANSIENT = "transient"
    # ESI's app-wide error limit, or our budget is paused or low.
    ERROR_LIMIT = "error_limit"


def classify(codes: list[int], error: BaseException | None = None) -> Outcome:
    """Outcome of one section from the ESI status codes it saw.

    Codes are EsiResponse.response_code: 0 is success, 9xx are client-side
    (see eveonline.client), the rest are HTTP statuses.
    """
    if isinstance(error, ESIErrorLimitException):
        return Outcome.ERROR_LIMIT
    if error is not None:
        return Outcome.TRANSIENT
    codes = [c for c in codes if isinstance(c, int)]
    if 420 in codes:
        return Outcome.ERROR_LIMIT
    if any(500 <= c < 600 for c in codes) or any(
        c in (901, 906) for c in codes
    ):
        return Outcome.TRANSIENT
    if any(c in (902, 904) for c in codes):
        return Outcome.SUSPENDED
    if 905 in codes:
        return Outcome.NO_SCOPE
    if any(400 <= c < 500 for c in codes):
        return Outcome.FAILED
    return Outcome.OK


def _jittered(interval: timedelta) -> timedelta:
    return interval * random.uniform(1 - JITTER, 1 + JITTER)


# The golden ratio's fractional part spreads consecutive ids evenly over
# [0, 1), so pilots' slots spread evenly over the interval.
_GOLDEN = (math.sqrt(5) - 1) / 2


def next_slot(now: datetime, interval: timedelta, key: int) -> datetime:
    """The character's next fixed slot at least half an interval away.

    Each character keeps the same offset within the interval, so pulls are
    spread evenly over time instead of drifting into bunches, and one
    pilot's pulls keep a steady rhythm.
    """
    seconds = interval.total_seconds()
    phase = (key * _GOLDEN % 1) * seconds
    earliest = now.timestamp() + seconds / 2
    slot = phase + math.ceil((earliest - phase) / seconds) * seconds
    return datetime.fromtimestamp(slot, tz=now.tzinfo)


def stamp(
    row: EveCharacterSyncState,
    outcome: Outcome,
    interval: timedelta,
    *,
    now=None,
    detail: str = "",
    slot_key: int | None = None,
) -> None:
    """Record one section's outcome on its row (not saved). With
    ``slot_key``, a success is next due at the character's fixed slot
    (``next_slot``) instead of a jittered interval."""
    now = now or timezone.now()
    row.queued_at = None
    row.attempted_at = now
    if outcome == Outcome.OK:
        row.synced_at = now
        row.consecutive_failures = 0
        row.last_error = ""
        if slot_key is None:
            row.next_due_at = now + _jittered(interval)
        else:
            row.next_due_at = next_slot(now, interval, slot_key)
        return
    if outcome in (Outcome.NO_SCOPE, Outcome.SUSPENDED):
        row.last_error = outcome.value
        row.next_due_at = now + interval
        return
    row.consecutive_failures += 1
    row.last_error = f"{outcome.value} {detail}".strip()[:255]
    if row.consecutive_failures >= QUICK_RETRIES:
        row.next_due_at = now + interval
    elif outcome == Outcome.FAILED:
        row.next_due_at = now + FAILURE_RETRY
    else:
        row.next_due_at = now + TRANSIENT_RETRY


def has_scopes(character: EveCharacter, section: Section) -> bool:
    return all(
        Token.get_token(character.character_id, list(scopes))
        for scopes in section.scopes
    )


def budget_available() -> bool:
    if esi_budget.pause_remaining(None) > 0:
        return False
    return esi_budget.error_budget() >= esi_budget.ERROR_BUDGET_FLOOR


def run_character_sync(
    character: EveCharacter,
    *,
    sections: Iterable[str] | None = None,
    force: bool = False,
    lock: bool = True,
    audiences: Audiences | None = None,
) -> dict:
    """Run a character's due sections in order and stamp each one.

    ``force`` runs every section (or every named one) whatever its
    ``next_due_at``; a character that has never synced anything is always
    forced. ``lock=False`` is for inline callers that must not wait, such
    as the tribes refresh button.
    """
    if not lock:
        return _run_character_sync(character, sections, force, audiences)
    with single_flight(
        f"character-sync:{character.pk}", SYNC_LOCK_SECONDS
    ) as acquired:
        if not acquired:
            if force:
                mark_due([character.pk], sections or SECTIONS_BY_NAME.keys())
            return {"skipped": "running"}
        return _run_character_sync(character, sections, force, audiences)


def _run_character_sync(character, sections, force, audiences) -> dict:
    if get_esi_downtime_countdown() > 0:
        return {"skipped": "downtime"}
    wanted = set(sections) if sections is not None else None
    audiences = audiences or load_audiences([character.pk])
    rows = {row.section: row for row in character.sync_states.all()}
    if not any(row.attempted_at for row in rows.values()):
        force = True
    summary: Counter = Counter()
    stopped = None
    for section in SECTIONS:
        if wanted is not None and section.name not in wanted:
            continue
        now = timezone.now()
        interval = audiences.interval(section, character.pk)
        row = rows.get(section.name) or EveCharacterSyncState(
            character=character, section=section.name, next_due_at=now
        )
        if not force and row.pk and row.next_due_at > now:
            continue
        if character.esi_suspended:
            outcome = Outcome.SUSPENDED
        elif not has_scopes(character, section):
            outcome = Outcome.NO_SCOPE
        elif not budget_available():
            stopped = Outcome.ERROR_LIMIT
            break
        else:
            outcome, detail = _run_section(character, section)
            if outcome == Outcome.ERROR_LIMIT:
                stopped = outcome
                break
            interval, slot_key = _stamp_timing(
                character, section, outcome, interval, now
            )
            stamp(
                row,
                outcome,
                interval,
                now=timezone.now(),
                detail=detail,
                slot_key=slot_key,
            )
            row.save()
            summary[outcome.value] += 1
            if outcome == Outcome.TRANSIENT:
                stopped = outcome
                break
            continue
        stamp(row, outcome, interval, now=now)
        row.save()
        summary[outcome.value] += 1
    result = dict(summary)
    if stopped:
        result["stopped"] = stopped.value
    return result


def _stamp_timing(character, section, outcome, interval, started):
    """The interval and slot to stamp with. Mining pulls keep the pilot's
    fixed slot, and one that found new ore makes the pilot hot."""
    if section.name != MINING:
        return interval, None
    if outcome == Outcome.OK and mined_recently(character.pk, started):
        interval = MINING_HOT_INTERVAL
    return interval, character.character_id


def _run_section(
    character: EveCharacter, section: Section
) -> tuple[Outcome, str]:
    error = None
    with record_esi_outcomes() as codes:
        try:
            section.run(character)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            error = exc
            if not isinstance(exc, ESIErrorLimitException):
                logger.exception(
                    "Character sync %s failed for %s",
                    section.name,
                    character.character_id,
                )
    outcome = classify(codes, error)
    failing = sorted({c for c in codes if c not in (0, None)})
    detail = ",".join(str(c) for c in failing)
    if error is not None and not detail:
        detail = type(error).__name__
    return outcome, detail


def mark_due(character_pks: Iterable[int], sections: Iterable[str], when=None):
    """Bring sections forward to ``when`` (default now). Never pushes later."""
    when = when or timezone.now()
    return EveCharacterSyncState.objects.filter(
        character_id__in=list(character_pks),
        section__in=list(sections),
        next_due_at__gt=when,
    ).update(next_due_at=when)


# Reporting


@dataclass
class SectionFreshness:
    section: str
    in_scope: int = 0
    overdue: int = 0
    failing: int = 0
    p95_age_hours: float | None = None
    oldest_age_hours: float | None = None
    top_errors: list[tuple[str, int]] = field(default_factory=list)

    @property
    def overdue_ratio(self) -> float:
        return self.overdue / self.in_scope if self.in_scope else 0.0


def freshness_report(audiences: Audiences | None = None) -> dict:
    """Per section: in-scope rows, overdue (older than 2x interval), ages,
    failures; plus recently added characters with nothing synced."""
    audiences = audiences or load_audiences()
    now = timezone.now()
    report = {s.name: SectionFreshness(s.name) for s in SECTIONS}
    ages: dict[str, list[float]] = {s.name: [] for s in SECTIONS}
    errors: dict[str, Counter] = {s.name: Counter() for s in SECTIONS}
    rows = EveCharacterSyncState.objects.values_list(
        "character_id",
        "section",
        "synced_at",
        "attempted_at",
        "last_error",
        "consecutive_failures",
    ).iterator(chunk_size=5000)
    for pk, name, synced_at, attempted_at, last_error, failures in rows:
        section = SECTIONS_BY_NAME.get(name)
        if section is None or not audiences.in_scope(name, pk):
            continue
        if last_error in (Outcome.NO_SCOPE.value, Outcome.SUSPENDED.value):
            continue
        entry = report[name]
        entry.in_scope += 1
        interval = audiences.interval(section, pk)
        reference = synced_at or attempted_at
        if synced_at is not None:
            ages[name].append((now - synced_at).total_seconds() / 3600)
        if reference is None or now - reference > 2 * interval:
            entry.overdue += 1
        if failures:
            entry.failing += 1
            errors[name][last_error.split(" ")[0] or "unknown"] += 1
    for name, entry in report.items():
        values = sorted(ages[name])
        if values:
            entry.p95_age_hours = round(
                values[min(len(values) - 1, int(len(values) * 0.95))], 2
            )
            entry.oldest_age_hours = round(values[-1], 2)
        entry.top_errors = errors[name].most_common(3)
    return {"sections": report, "unsynced_new": unsynced_new_characters()}


def unsynced_new_characters(
    since: timedelta = timedelta(days=1),
    grace: timedelta = timedelta(minutes=10),
) -> list[int]:
    """EVE ids of characters added recently (past ``grace``) with a token
    whose first fetch was never attempted."""
    now = timezone.now()
    return list(
        EveCharacter.objects.filter(
            created_at__gte=now - since,
            created_at__lte=now - grace,
            esi_deleted=False,
            esi_suspended=False,
        )
        .exclude(token=None)
        .exclude(sync_states__attempted_at__isnull=False)
        .values_list("character_id", flat=True)
    )


def token_scope_sets(character_ids: Iterable[int]) -> dict[int, list[set]]:
    """EVE character id -> the scope sets of each of its tokens."""
    result: dict[int, list[set]] = {}
    tokens = Token.objects.filter(
        character_id__in=list(character_ids)
    ).prefetch_related("scopes")
    for token in tokens:
        result.setdefault(token.character_id, []).append(
            {scope.name for scope in token.scopes.all()}
        )
    return result


def granted(scope_sets: list[set], section: Section) -> bool:
    return all(
        any(set(scopes) <= token_scopes for token_scopes in scope_sets)
        for scopes in section.scopes
    )
