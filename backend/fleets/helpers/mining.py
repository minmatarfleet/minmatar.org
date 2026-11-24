"""Mining fleet tracking: ledger readings per member stint, and results.

A fleet with ``track_mining`` gives each member one ``EveFleetMiningSegment``
per stint in the in-game fleet:

- start reading when the member poll first lists the pilot (or lists them
  again after they left);
- a live reading about every ``MINING_POLL_INTERVAL`` while the fleet runs;
- an end reading ``MINING_LEDGER_LAG_SECONDS`` after the pilot leaves or the
  fleet ends, so ore mined in the last minutes reaches the ESI ledger.

A reading syncs the pilot's ESI mining ledger, then sums every ledger row
dated on or after the stint's start day, in any system. Ore mined in a stint
is ``latest_totals - start_totals`` per ore type.
See docs/fleets/mining-tracking.md.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import timedelta
from typing import Callable

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from esi.models import Token
from eveuniverse.models import EveType

from eveonline.helpers.characters.mining import (
    mining_totals_since,
    sync_character_mining,
)
from eveonline.models import EveCharacter, EveCharacterMiningDelta
from fleets.models import (
    EveFleet,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetMiningSegment,
)
from market.helpers.pricing import get_history_averages_by_type_id

logger = logging.getLogger(__name__)

MINING_SCOPE = ["esi-industry.read_character_mining.v1"]
# ESI caches the mining ledger for about 10 minutes (TO CONFIRM), so the end
# reading waits a little longer than that.
MINING_LEDGER_LAG_SECONDS = 11 * 60
# Live readings: no faster than the ledger cache, which would read the same
# numbers again.
MINING_POLL_INTERVAL = timedelta(minutes=15)
# A start reading still missing this long after the stint began is retried.
START_RETRY_AFTER = timedelta(minutes=2)
# An end reading whose task was lost is forced this long after it was due.
END_FORCE_AFTER = timedelta(minutes=30)
POLL_SPREAD_SECONDS = 4 * 60

Segment = EveFleetMiningSegment


def has_mining_scope(character_id: int) -> bool:
    return Token.get_token(character_id, MINING_SCOPE) is not None


def _character(member: EveFleetInstanceMember) -> EveCharacter | None:
    return EveCharacter.objects.filter(
        character_id=member.character_id
    ).first()


def _queue(task_name: str, segment_id: int, countdown: int = 0) -> None:
    """Queue a reading once the current transaction commits."""
    # pylint: disable=import-outside-toplevel
    from fleets import tasks

    task = getattr(tasks, task_name)
    transaction.on_commit(
        lambda: task.apply_async(args=[segment_id], countdown=countdown)
    )


# ---------------------------------------------------------------- segments


def has_open_segment(member: EveFleetInstanceMember) -> bool:
    return member.mining_segments.filter(ended_at__isnull=True).exists()


def open_segment(member: EveFleetInstanceMember, now=None) -> Segment:
    """Start a stint for a member (idempotent while one is open)."""
    existing = member.mining_segments.filter(ended_at__isnull=True).first()
    if existing:
        return existing
    now = now or timezone.now()
    scoped = _character(member) is not None and has_mining_scope(
        member.character_id
    )
    segment = Segment.objects.create(
        member=member,
        status=Segment.STATUS_PENDING if scoped else Segment.STATUS_NO_SCOPE,
        started_at=now,
        # timezone.now() is UTC, which is EVE time: the ledger's day.
        since_date=now.date(),
    )
    if scoped:
        _queue("fleet_mining_start_reading", segment.id)
    return segment


def close_segment(segment: Segment, now=None) -> None:
    """End a stint; its end reading is queued after the ledger lag."""
    now = now or timezone.now()
    if segment.ended_at is not None:
        return
    segment.ended_at = now
    if segment.status in (Segment.STATUS_PENDING, Segment.STATUS_OPEN):
        segment.status = Segment.STATUS_CLOSING
        segment.save(update_fields=["ended_at", "status"])
        _queue(
            "fleet_mining_end_reading",
            segment.id,
            countdown=MINING_LEDGER_LAG_SECONDS,
        )
    else:
        segment.save(update_fields=["ended_at"])


def close_member_segments(member: EveFleetInstanceMember, now=None) -> None:
    for segment in member.mining_segments.filter(ended_at__isnull=True):
        close_segment(segment, now)


def close_open_segments(eve_fleet: EveFleet, now=None) -> int:
    """End every open stint of a fleet (it ended or was cancelled)."""
    now = now or timezone.now()
    segments = list(
        Segment.objects.filter(
            member__eve_fleet_instance__eve_fleet=eve_fleet,
            ended_at__isnull=True,
        )
    )
    for segment in segments:
        close_segment(segment, now)
    return len(segments)


# ---------------------------------------------------------------- readings


def _read(segment: Segment) -> dict[str, int] | None:
    """Fresh per-ore totals for the stint, or None when ESI didn't answer."""
    character = _character(segment.member)
    if character is None:
        return None
    if sync_character_mining(character) is None:
        return None
    return mining_totals_since(character, segment.since_date)


def _merge_max(old: dict | None, new: dict) -> dict:
    """Ledger totals only grow; a lower number is a stale cache, not a fact."""
    merged = dict(old or {})
    for key, value in new.items():
        merged[key] = max(int(merged.get(key, 0)), int(value))
    return merged


def take_start_reading(segment_id: int) -> bool:
    """True once the stint has a start reading (or no longer needs one)."""
    segment = Segment.objects.select_related("member").get(pk=segment_id)
    if segment.start_totals is not None:
        return True
    if segment.status not in (Segment.STATUS_PENDING, Segment.STATUS_CLOSING):
        return True
    totals = _read(segment)
    if totals is None:
        return False
    now = timezone.now()
    Segment.objects.filter(pk=segment_id, start_totals__isnull=True).update(
        start_totals=totals,
        latest_totals=totals,
        start_read_at=now,
        latest_read_at=now,
    )
    Segment.objects.filter(
        pk=segment_id, status=Segment.STATUS_PENDING
    ).update(status=Segment.STATUS_OPEN)
    return True


def take_poll_reading(segment_id: int) -> bool:
    """Live reading for an open stint."""
    segment = Segment.objects.select_related("member").get(pk=segment_id)
    if segment.status != Segment.STATUS_OPEN:
        return True
    totals = _read(segment)
    if totals is None:
        return False
    with transaction.atomic():
        segment = Segment.objects.select_for_update().get(pk=segment_id)
        if segment.status not in (Segment.STATUS_OPEN, Segment.STATUS_CLOSING):
            return True
        segment.latest_totals = _merge_max(segment.latest_totals, totals)
        segment.latest_read_at = timezone.now()
        segment.save(update_fields=["latest_totals", "latest_read_at"])
    return True


def take_end_reading(segment_id: int, *, final: bool = False) -> bool:
    """
    Final reading for a closing stint. On the last try (``final``) a stint
    ESI won't answer for closes on its last good poll (``closed_stale``).
    """
    segment = Segment.objects.select_related("member").get(pk=segment_id)
    if segment.status != Segment.STATUS_CLOSING:
        return True
    if segment.start_totals is None:
        # The start reading never landed: nothing to subtract from.
        if final:
            segment.status = Segment.STATUS_FAILED
            segment.save(update_fields=["status"])
            return True
        if not take_start_reading(segment_id):
            return False
        return False  # read again later: this reading is the start
    totals = _read(segment)
    with transaction.atomic():
        segment = Segment.objects.select_for_update().get(pk=segment_id)
        if segment.status != Segment.STATUS_CLOSING:
            return True
        if totals is None:
            if not final:
                return False
            segment.status = Segment.STATUS_CLOSED_STALE
            segment.save(update_fields=["status"])
            return True
        segment.latest_totals = _merge_max(segment.latest_totals, totals)
        segment.latest_read_at = timezone.now()
        segment.status = Segment.STATUS_CLOSED
        segment.save(
            update_fields=["latest_totals", "latest_read_at", "status"]
        )
    return True


def due_segments(now=None) -> dict[str, list[int]]:
    """Stints that need a reading now, by kind."""
    now = now or timezone.now()
    live = Q(member__eve_fleet_instance__end_time__isnull=True)
    return {
        "start": list(
            Segment.objects.filter(
                live,
                status=Segment.STATUS_PENDING,
                started_at__lte=now - START_RETRY_AFTER,
            ).values_list("id", flat=True)
        ),
        "poll": list(
            Segment.objects.filter(live, status=Segment.STATUS_OPEN)
            .filter(
                Q(latest_read_at__isnull=True)
                | Q(
                    latest_read_at__lte=now
                    - MINING_POLL_INTERVAL
                    + timedelta(minutes=1)
                )
            )
            .values_list("id", flat=True)
        ),
        # The end task should have run; it may have been lost.
        "end": list(
            Segment.objects.filter(
                status=Segment.STATUS_CLOSING,
                ended_at__lte=now
                - timedelta(seconds=MINING_LEDGER_LAG_SECONDS)
                - END_FORCE_AFTER,
            ).values_list("id", flat=True)
        ),
    }


# ---------------------------------------------------------------- results

PILOT_MEASURING = "measuring"
PILOT_DONE = "done"
PILOT_PARTIAL = "partial"
PILOT_NO_SCOPE = "no_scope"


def _pilot_status(statuses: set[str]) -> str:
    if statuses & set(Segment.ACTIVE_STATUSES):
        return PILOT_MEASURING
    if statuses == {Segment.STATUS_NO_SCOPE}:
        return PILOT_NO_SCOPE
    if statuses & {Segment.STATUS_CLOSED_STALE, Segment.STATUS_FAILED}:
        return PILOT_PARTIAL
    return PILOT_DONE


def _segment_ore(segment: Segment) -> dict[int, int]:
    if segment.start_totals is None or segment.latest_totals is None:
        return {}
    ore = {}
    for key, latest in segment.latest_totals.items():
        mined = int(latest) - int(segment.start_totals.get(key, 0))
        if mined > 0:
            ore[int(key)] = mined
    return ore


def _ore_lines(quantities: dict[int, int], types, prices) -> list[dict]:
    lines = []
    for type_id, quantity in quantities.items():
        eve_type = types.get(type_id)
        volume = float(eve_type.volume or 0) if eve_type else 0.0
        price = float(prices.get(type_id) or 0)
        lines.append(
            {
                "type_id": type_id,
                "name": eve_type.name if eve_type else str(type_id),
                "quantity": quantity,
                "volume_m3": round(quantity * volume, 2),
                "isk_estimate": round(quantity * price, 2),
            }
        )
    lines.sort(key=lambda line: line["volume_m3"], reverse=True)
    return lines


def fleet_mining_results(
    fleet: EveFleet, visible: Callable[[int], bool]
) -> dict:
    """
    Ore per pilot for a fleet, from every tracked instance. Pilots the
    viewer may not name (``visible`` False) keep their ore but lose their
    name and id. Totals count everyone.
    """
    segments = Segment.objects.filter(
        member__eve_fleet_instance__eve_fleet=fleet
    ).select_related("member")

    names: dict[int, str] = {}
    statuses: dict[int, set] = defaultdict(set)
    ore: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    updated_at = None
    for segment in segments:
        character_id = segment.member.character_id
        names[character_id] = segment.member.character_name
        statuses[character_id].add(segment.status)
        for type_id, quantity in _segment_ore(segment).items():
            ore[character_id][type_id] += quantity
        if segment.latest_read_at and (
            updated_at is None or segment.latest_read_at > updated_at
        ):
            updated_at = segment.latest_read_at

    type_ids = {t for per_pilot in ore.values() for t in per_pilot}
    types = EveType.objects.in_bulk(list(type_ids))
    prices = get_history_averages_by_type_id(list(type_ids))

    pilots = []
    fleet_ore: dict[int, int] = defaultdict(int)
    for character_id, name in names.items():
        lines = _ore_lines(dict(ore[character_id]), types, prices)
        for line in lines:
            fleet_ore[line["type_id"]] += line["quantity"]
        shown = visible(character_id)
        pilots.append(
            {
                "character_id": character_id if shown else None,
                "character_name": name if shown else None,
                "status": _pilot_status(statuses[character_id]),
                "ores": lines,
                "volume_m3": round(sum(x["volume_m3"] for x in lines), 2),
                "isk_estimate": round(
                    sum(x["isk_estimate"] for x in lines), 2
                ),
            }
        )
    pilots.sort(key=lambda p: (-p["volume_m3"], p["character_name"] or "~"))

    fleet_lines = _ore_lines(dict(fleet_ore), types, prices)
    return {
        "track_mining": bool(fleet.track_mining),
        "measuring": any(p["status"] == PILOT_MEASURING for p in pilots),
        "updated_at": updated_at,
        "pilots": pilots,
        "ores": fleet_lines,
        "volume_m3": round(sum(x["volume_m3"] for x in fleet_lines), 2),
        "isk_estimate": round(sum(x["isk_estimate"] for x in fleet_lines), 2),
        "pilots_no_scope": sum(
            1 for p in pilots if p["status"] == PILOT_NO_SCOPE
        ),
    }


# ---------------------------------------------------------------- timeline
#
# The dispatch view: ore per pilot per time bucket. It reads the ledger
# deltas every sync stores (EveCharacterMiningDelta, "+X ore seen at T"),
# both the character-sync scheduler's pulls and this module's readings. A
# delta belongs to a stint when it was seen after the stint's start reading
# and no later than its last reading; one seen by the end reading (taken
# after the pilot left) is drawn in the stint's last bucket.

BUCKET = timedelta(minutes=15)
# In the fleet with no ore for this many buckets in a row: idle. One empty
# bucket alone may only mean no pull landed in it.
IDLE_BUCKETS = 2
MAX_EVENTS = 200

CELL_ORE = "ore"
CELL_QUIET = "quiet"
CELL_IDLE = "idle"
CELL_OUT = "out"


def _fleet_window(fleet: EveFleet, now):
    instances = list(EveFleetInstance.objects.filter(eve_fleet=fleet))
    if not instances:
        return None, None
    start = min(i.start_time for i in instances)
    ends = [i.end_time for i in instances]
    end = now if any(e is None for e in ends) else max(ends)
    return start, max(end, start)


def _mark_idle(cells: list[str]) -> list[str]:
    """Runs of IDLE_BUCKETS or more empty in-fleet buckets become idle."""
    out = list(cells)
    run: list[int] = []
    for index, cell in enumerate(cells + [CELL_OUT]):
        if cell == CELL_QUIET:
            run.append(index)
            continue
        if len(run) >= IDLE_BUCKETS:
            for i in run:
                out[i] = CELL_IDLE
        run = []
    return out


class _Buckets:
    """The fleet's 15-minute slots from its first start to its end (or now)."""

    def __init__(self, start, end):
        # Slots start when the fleet does, so the first one is a full slot
        # rather than a sliver before a clock quarter-hour.
        self.first = start.replace(second=0, microsecond=0)
        # Every slot the fleet touched, the running one included; no empty
        # slot after a fleet that ends on a slot boundary.
        # (A last slot under a minute long is folded into the one before.)
        self.count = max(
            1, math.ceil((end - self.first - timedelta(minutes=1)) / BUCKET)
        )

    def index(self, moment) -> int:
        return min(self.count - 1, max(0, int((moment - self.first) / BUCKET)))

    def starts(self) -> list:
        return [self.first + BUCKET * i for i in range(self.count)]


def _deltas_by_character(segments, characters: dict[int, int]):
    """{character pk: [(type_id, quantity, observed_at)]} after any start."""
    deltas = defaultdict(list)
    starts = [s.start_read_at for s in segments if s.start_read_at]
    if not starts:
        return deltas
    rows = EveCharacterMiningDelta.objects.filter(
        character_id__in=list(characters.values()),
        observed_at__gt=min(starts),
    ).values_list("character_id", "eve_type_id", "quantity", "observed_at")
    for character_pk, type_id, quantity, observed_at in rows:
        deltas[character_pk].append((type_id, quantity, observed_at))
    return deltas


def _event(kind: str, at, pilot: dict, **fields) -> dict:
    return {
        "at": at,
        "kind": kind,
        "character_id": pilot["character_id"],
        "character_name": pilot["character_name"],
        **fields,
    }


def _stint_ore(segment, deltas, now):
    """The deltas that belong to a stint: after its start reading, up to its
    last reading once it has ended (the end reading is taken after the pilot
    left, so it holds their last minutes in the fleet)."""
    if segment.status == Segment.STATUS_NO_SCOPE or not segment.start_read_at:
        return
    upper = (
        segment.latest_read_at
        if segment.ended_at and segment.latest_read_at
        else now
    )
    for type_id, quantity, observed_at in deltas:
        if segment.start_read_at < observed_at <= upper:
            yield type_id, quantity, observed_at


def _unseen_ore(segment, ore: list) -> list:
    """Ore the readings counted but no delta row timed (pulls from before
    delta rows were stored). It is drawn when the timed ore starts, or at
    the last reading when there is none, so the chart's total matches the
    readings'."""
    if not segment.latest_read_at:
        return []
    timed: dict[int, int] = defaultdict(int)
    for type_id, quantity, _ in ore:
        timed[type_id] += quantity
    at = min((o[2] for o in ore), default=segment.latest_read_at)
    return [
        (type_id, quantity - timed[type_id], at)
        for type_id, quantity in _segment_ore(segment).items()
        if quantity > timed[type_id]
    ]


def _pilot_row(pilot: dict) -> dict:
    cells = [
        (CELL_OUT if not in_fleet else CELL_ORE if m3 > 0 else CELL_QUIET)
        for in_fleet, m3 in zip(pilot["in_fleet"], pilot["cell_m3"])
    ]
    if not pilot["no_scope"]:
        cells = _mark_idle(cells)
    in_fleet = sum(1 for c in cells if c != CELL_OUT)
    with_ore = sum(1 for c in cells if c == CELL_ORE)
    return {
        "character_id": pilot["character_id"],
        "character_name": pilot["character_name"],
        "no_scope": pilot["no_scope"],
        "cells": cells,
        "cell_m3": [round(v, 2) for v in pilot["cell_m3"]],
        "volume_m3": round(sum(pilot["cell_m3"]), 2),
        "mining_pct": (
            None
            if pilot["no_scope"] or not in_fleet
            else round(100 * with_ore / in_fleet)
        ),
    }


def fleet_mining_timeline(
    fleet: EveFleet, visible: Callable[[int], bool], now=None
) -> dict | None:
    """Per-pilot ore per bucket, fleet totals and a log; None before start."""
    now = now or timezone.now()
    start, end = _fleet_window(fleet, now)
    if start is None:
        return None
    slots = _Buckets(start, end)

    segments = sorted(
        Segment.objects.filter(
            member__eve_fleet_instance__eve_fleet=fleet
        ).select_related("member"),
        key=lambda s: s.started_at,
    )
    characters = dict(
        EveCharacter.objects.filter(
            character_id__in={s.member.character_id for s in segments}
        ).values_list("character_id", "pk")
    )
    deltas = _deltas_by_character(segments, characters)
    types = EveType.objects.in_bulk(
        list(
            {row[0] for rows in deltas.values() for row in rows}
            | {int(k) for s in segments for k in (s.latest_totals or {})}
        )
    )

    pilots: dict[int, dict] = {}
    events: list[dict] = []
    for segment in segments:
        character_id = segment.member.character_id
        shown = visible(character_id)
        pilot = pilots.setdefault(
            character_id,
            {
                "character_id": character_id if shown else None,
                "character_name": (
                    segment.member.character_name if shown else None
                ),
                "no_scope": True,
                "in_fleet": [False] * slots.count,
                "cell_m3": [0.0] * slots.count,
            },
        )
        stint_end = segment.ended_at or end
        for i in range(
            slots.index(segment.started_at), slots.index(stint_end) + 1
        ):
            pilot["in_fleet"][i] = True
        events.append(_event("join", segment.started_at, pilot))
        if segment.ended_at:
            events.append(_event("leave", segment.ended_at, pilot))
        if segment.status != Segment.STATUS_NO_SCOPE:
            pilot["no_scope"] = False
        ore = list(
            _stint_ore(
                segment, deltas.get(characters.get(character_id), []), now
            )
        )
        ore += _unseen_ore(segment, ore)
        for type_id, quantity, observed_at in ore:
            eve_type = types.get(type_id)
            m3 = quantity * float(eve_type.volume or 0) if eve_type else 0.0
            pilot["cell_m3"][slots.index(min(observed_at, stint_end))] += m3
            events.append(
                _event(
                    "ore",
                    observed_at,
                    pilot,
                    type_id=type_id,
                    ore_name=eve_type.name if eve_type else str(type_id),
                    quantity=quantity,
                    volume_m3=round(m3, 2),
                )
            )

    rows = sorted(
        (_pilot_row(p) for p in pilots.values()),
        key=lambda r: (
            r["no_scope"],
            -r["volume_m3"],
            r["character_name"] or "~",
        ),
    )
    events.sort(key=lambda e: e["at"], reverse=True)
    return {
        "bucket_minutes": int(BUCKET.total_seconds() // 60),
        "start": start,
        "end": end,
        "buckets": slots.starts(),
        "totals_m3": [
            round(sum(r["cell_m3"][i] for r in rows), 2)
            for i in range(slots.count)
        ],
        "pilots": rows,
        "events": events[:MAX_EVENTS],
    }
