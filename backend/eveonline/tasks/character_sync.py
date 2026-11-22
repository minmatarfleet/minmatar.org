"""Paced character sync: one scheduler queues characters whose sections are
due, within a per-tick budget. See docs/architecture/character-sync.md.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from app import monitoring
from app.celery import app
from eveonline import character_sync as sync
from eveonline import esi_budget
from eveonline.models import EveCharacter, EveCharacterSyncState
from eveonline.utils import get_esi_downtime_countdown

logger = logging.getLogger(__name__)

TICK_SECONDS = 60
# CHARACTER_SYNC_COST_PER_TICK is a budget per 5 minutes (it predates the
# one-minute tick); each tick spends its share, so pulls run all the time
# instead of in one burst every five minutes.
BUDGET_SECONDS = 5 * 60
# Due rows read per tick; far more than one tick's budget ever uses.
DUE_ROW_LIMIT = 5000
# Due rows for characters that left every audience are pushed this far out,
# so the tick stops reading them.
OUT_OF_SCOPE_PUSH = timedelta(days=1)
# A just-added character gets its first fetch from update_character_urgent;
# the scheduler leaves it alone this long.
NEW_CHARACTER_GRACE = timedelta(minutes=10)
# Health alert thresholds (docs/architecture/character-sync.md)
OVERDUE_ALERT_RATIO = 0.05


@app.task(expires=10 * 60)
def sync_character_sections(character_id: int) -> dict:
    """Run one character's due sections and stamp them."""
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if character is None or character.esi_deleted:
        return {"skipped": "missing"}
    return sync.run_character_sync(character)


@app.task(expires=TICK_SECONDS)
def queue_due_character_syncs() -> dict:
    """Queue characters with due sections, oldest first, within the budget.

    Does nothing in fanout mode; logs only in shadow mode.
    """
    mode = sync.sync_mode()
    if mode == sync.MODE_FANOUT:
        return {"mode": mode}
    if get_esi_downtime_countdown() > 0:
        return {"mode": mode, "skipped": "downtime"}
    if esi_budget.pause_remaining(None) > 0:
        return {"mode": mode, "skipped": "esi paused"}

    plan = plan_tick(sync.load_audiences())
    shadow = mode == sync.MODE_SHADOW
    summary = {
        "mode": mode,
        "characters": len(plan.character_ids),
        "cost": plan.cost,
        "budget": plan.budget,
        "due_characters": plan.due_characters,
        "new_characters": len(plan.new_pks),
        "out_of_scope_rows": len(plan.out_of_scope_rows),
        "oldest_due_minutes": plan.oldest_due_minutes,
        "due_by_section": plan.due_by_section,
    }
    for name, count in plan.due_by_section.items():
        monitoring.gauge("character_sync.due", count, section=name)
    monitoring.gauge("character_sync.queued", len(plan.character_ids))
    if shadow:
        logger.info("Character sync shadow tick: %s", summary)
        return summary

    apply_plan(plan)
    count = len(plan.character_ids)
    for index, character_id in enumerate(plan.character_ids):
        sync_character_sections.apply_async(
            args=[character_id],
            countdown=int(index * TICK_SECONDS / max(count, 1)),
        )
    logger.info("Character sync tick: %s", summary)
    return summary


def tick_budget() -> int:
    per_budget = getattr(settings, "CHARACTER_SYNC_COST_PER_TICK", 300)
    return max(1, round(per_budget * TICK_SECONDS / BUDGET_SECONDS))


class TickPlan:
    def __init__(self, budget: int):
        self.budget = budget
        self.cost = 0
        self.character_ids: list[int] = []
        self.lease_row_pks: list[int] = []
        # Characters with no rows yet: (pk, queued now?)
        self.new_pks: list[int] = []
        self.queued_new_pks: set[int] = set()
        self.out_of_scope_rows: list[int] = []
        self.due_characters = 0
        self.due_by_section: dict[str, int] = {}
        self.oldest_due_minutes: float | None = None


def plan_tick(audiences: sync.Audiences, now=None) -> TickPlan:
    """Choose this tick's characters. Reads only; ``apply_plan`` writes."""
    now = now or timezone.now()
    plan = TickPlan(tick_budget())
    eligible = audiences.eligible()
    suspended = set(
        EveCharacter.objects.filter(
            pk__in=eligible, esi_suspended=True
        ).values_list("pk", flat=True)
    )
    eligible -= suspended
    lease_cutoff = now - sync.QUEUED_LEASE

    # Characters with no rows at all (new members), and recently added
    # characters (applicants) whose first fetch was never attempted, e.g.
    # because it ran during ESI downtime.
    with_rows = set(
        EveCharacterSyncState.objects.values_list(
            "character_id", flat=True
        ).distinct()
    )
    recent_unsynced = set(
        EveCharacter.objects.filter(
            created_at__gte=now - sync.NEW_CHARACTER_WINDOW,
            esi_deleted=False,
            esi_suspended=False,
        )
        .exclude(token=None)
        .exclude(sync_states__attempted_at__isnull=False)
        .exclude(sync_states__queued_at__gte=lease_cutoff)
        .values_list("pk", flat=True)
    )
    # Leave a just-added character to its own first fetch
    # (update_character_urgent, 30 s after the add) for a few minutes.
    just_added = set(
        EveCharacter.objects.filter(
            created_at__gt=now - NEW_CHARACTER_GRACE
        ).values_list("pk", flat=True)
    )
    new_pks = sorted(((eligible - with_rows) | recent_unsynced) - just_added)
    plan.new_pks = new_pks

    due_rows = list(
        EveCharacterSyncState.objects.filter(next_due_at__lte=now)
        .filter(Q(queued_at__isnull=True) | Q(queued_at__lt=lease_cutoff))
        .order_by("next_due_at")
        .values_list("pk", "character_id", "section", "next_due_at")[
            :DUE_ROW_LIMIT
        ]
    )

    per_character: dict[int, list[tuple[int, str]]] = {}
    order: list[int] = []
    for row_pk, pk, name, next_due_at in due_rows:
        if pk in recent_unsynced or pk in suspended:
            continue
        if name not in sync.SECTIONS_BY_NAME or not audiences.in_scope(
            name, pk
        ):
            plan.out_of_scope_rows.append(row_pk)
            continue
        if pk not in per_character:
            per_character[pk] = []
            order.append(pk)
            if plan.oldest_due_minutes is None:
                plan.oldest_due_minutes = round(
                    (now - next_due_at).total_seconds() / 60, 1
                )
        per_character[pk].append((row_pk, name))
        plan.due_by_section[name] = plan.due_by_section.get(name, 0) + 1
    plan.due_characters = len(order) + len(new_pks)

    full_cost = sum(section.weight for section in sync.SECTIONS)
    chosen_pks: list[int] = []
    for pk in new_pks:
        if plan.cost + full_cost > plan.budget and chosen_pks:
            break
        plan.cost += full_cost
        chosen_pks.append(pk)
        plan.queued_new_pks.add(pk)
    for pk in order:
        rows = per_character[pk]
        cost = sum(sync.SECTIONS_BY_NAME[name].weight for _, name in rows)
        if plan.cost + cost > plan.budget and chosen_pks:
            break
        plan.cost += cost
        chosen_pks.append(pk)
        plan.lease_row_pks.extend(row_pk for row_pk, _ in rows)

    ids = dict(
        EveCharacter.objects.filter(pk__in=chosen_pks).values_list(
            "pk", "character_id"
        )
    )
    plan.character_ids = [ids[pk] for pk in chosen_pks if pk in ids]
    return plan


def apply_plan(plan: TickPlan, now=None) -> None:
    """Lease the chosen rows and create rows for characters that have none."""
    now = now or timezone.now()
    for start in range(0, len(plan.lease_row_pks), 1000):
        EveCharacterSyncState.objects.filter(
            pk__in=plan.lease_row_pks[start : start + 1000]
        ).update(queued_at=now)
    for start in range(0, len(plan.out_of_scope_rows), 1000):
        EveCharacterSyncState.objects.filter(
            pk__in=plan.out_of_scope_rows[start : start + 1000]
        ).update(next_due_at=now + OUT_OF_SCOPE_PUSH)
    if plan.new_pks:
        existing = set(
            EveCharacterSyncState.objects.filter(
                character_id__in=plan.new_pks
            ).values_list("character_id", "section")
        )
        EveCharacterSyncState.objects.filter(
            character_id__in=plan.queued_new_pks
        ).update(queued_at=now)
        rows = [
            EveCharacterSyncState(
                character_id=pk,
                section=section.name,
                next_due_at=now,
                queued_at=now if pk in plan.queued_new_pks else None,
            )
            for pk in plan.new_pks
            for section in sync.SECTIONS
            if (pk, section.name) not in existing
        ]
        EveCharacterSyncState.objects.bulk_create(
            rows, batch_size=1000, ignore_conflicts=True
        )


@app.task(expires=15 * 60)
def report_character_sync_health() -> dict:
    """Gauge per-section freshness; warn when sections fall behind.

    Warnings only fire in scheduled mode: in fanout mode the 4-hourly run
    owns freshness and the table is informational.
    """
    report = sync.freshness_report()
    alerting = sync.sync_mode() == sync.MODE_SCHEDULED
    result = {}
    for name, entry in report["sections"].items():
        monitoring.gauge(
            "character_sync.overdue_ratio", entry.overdue_ratio, section=name
        )
        if entry.p95_age_hours is not None:
            monitoring.gauge(
                "character_sync.p95_age_hours",
                entry.p95_age_hours,
                section=name,
            )
        result[name] = {
            "in_scope": entry.in_scope,
            "overdue": entry.overdue,
            "failing": entry.failing,
        }
        if alerting and entry.overdue_ratio > OVERDUE_ALERT_RATIO:
            logger.warning(
                "Character sync %s behind: %s of %s characters older than "
                "twice their interval",
                name,
                entry.overdue,
                entry.in_scope,
            )
    unsynced = report["unsynced_new"]
    result["unsynced_new"] = len(unsynced)
    if alerting and unsynced:
        logger.warning(
            "Character sync: %s new character(s) not synced 10 minutes "
            "after they were added: %s",
            len(unsynced),
            unsynced[:20],
        )
    return result
