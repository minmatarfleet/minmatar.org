"""Build, store and serve a fleet's fight timeline.

A Celery tick rebuilds every fleet that is live or ended under
``SETTLE_AFTER`` ago, from scratch each time, so a restart or a late
killmail can never leave it half-updated. Twenty minutes after the fleet
ends, a zKillboard sweep fills in mails the live feed missed. Two hours
after, a last rebuild settles it and looks up eve-kill battles.

FC edits re-cut the stored killmails without matching again, so they are
cheap enough to run in the request.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta

import requests
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from eveonline.helpers.characters import user_primary_character
from feed.helpers.ingest import upsert_feed_killmail_from_raw
from feed.helpers.zkill_client import (
    ZKILL_API_BASE,
    fetch_esi_killmail,
    headers,
    zkill_get,
)
from feed.models import FeedKillmail, FeedR2z2Cursor
from fleets.helpers.fights.collect import (
    collect_events,
    collect_rows,
    resolve_names,
)
from fleets.helpers.fights.rounds import build_payload, parse_time

logger = logging.getLogger(__name__)

SETTLE_AFTER = timedelta(hours=2)
SWEEP_AFTER = timedelta(minutes=20)
# An open instance the poller stopped touching is not live any more.
LIVE_STALE_AFTER = timedelta(minutes=30)
EXCLUDED_FLEET_TYPES = ("standing",)
# The feed is "behind" when its poller has not reached zKill for this long.
FEED_BEHIND_AFTER = timedelta(minutes=3)

SWEEP_GROUPS = 3
SWEEP_MAX_PAGES = 5
SWEEP_SLEEP_SECONDS = 1.1
ZKILL_MAX_PAST_SECONDS = 7 * 24 * 3600
# Alliance ids start here; anything lower is a corporation.
FIRST_ALLIANCE_ID = 99000000
EVEKILL_BATTLE_URL = "https://eve-kill.com/api/battle/killmail/{killmail_id}"


def _instances(fleet):
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstance

    return EveFleetInstance.objects.filter(eve_fleet=fleet)


def is_live(fleet, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    return (
        _instances(fleet)
        .filter(
            end_time__isnull=True, last_updated__gte=now - LIVE_STALE_AFTER
        )
        .exists()
    )


def _edit_rows(fleet) -> list[dict]:
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetFightEdit

    rows = []
    for edit in EveFleetFightEdit.objects.filter(
        eve_fleet=fleet
    ).select_related("created_by"):
        character = (
            user_primary_character(edit.created_by)
            if edit.created_by
            else None
        )
        rows.append(
            {
                "id": edit.id,
                "kind": edit.kind,
                "start": edit.start,
                "end": edit.end,
                "created_by": character.character_name if character else None,
                "created_at": edit.created_at.isoformat(),
            }
        )
    return rows


def _bounds(events: list[dict]) -> tuple[datetime | None, datetime | None]:
    start = end = None
    for event in events:
        if event["kind"] == "start":
            start = parse_time(event["at"])
        elif event["kind"] == "end":
            end = parse_time(event["at"])
    return start, end


def recut(timeline, *, now: datetime | None = None, save: bool = True):
    """Cut the stored killmails into rounds with the current edits."""
    now = now or timezone.now()
    start, end = _bounds(timeline.events)
    if start is None:
        return timeline
    live = end is None and is_live(timeline.eve_fleet, now)
    if end is None and not live:
        # Tracking stopped without an end time; stop the clock at the last
        # time the poller saw the fleet.
        last = (
            _instances(timeline.eve_fleet)
            .order_by("-last_updated")
            .values_list("last_updated", flat=True)
            .first()
        )
        end = last or now
    timeline.payload = build_payload(
        timeline.killmails,
        events=timeline.events,
        names=timeline.names,
        edits=_edit_rows(timeline.eve_fleet),
        battles=timeline.battle_links,
        start=start,
        end=end,
        now=now,
    )
    if save:
        timeline.save(update_fields=["payload"])
    return timeline


def rebuild(fleet, *, now: datetime | None = None):
    """Match the fleet's killmails again and re-cut them."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetFightTimeline

    now = now or timezone.now()
    timeline, _ = EveFleetFightTimeline.objects.get_or_create(eve_fleet=fleet)
    rows, our_groups, instances = collect_rows(fleet)
    if not instances:
        return timeline
    timeline.killmails = rows
    timeline.names = resolve_names(rows, our_groups, timeline.names)
    timeline.events = collect_events(instances)
    timeline.computed_at = now
    recut(timeline, now=now, save=False)
    timeline.save()
    return timeline


def due_fleet_ids(now: datetime | None = None) -> list[int]:
    """Fleets that are live, or ended and not settled yet."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstance

    now = now or timezone.now()
    return list(
        EveFleetInstance.objects.filter(
            Q(end_time__isnull=True, last_updated__gte=now - LIVE_STALE_AFTER)
            | Q(end_time__gte=now - SETTLE_AFTER - timedelta(minutes=30))
        )
        .exclude(eve_fleet__type__in=EXCLUDED_FLEET_TYPES)
        .exclude(eve_fleet__fight_timeline__settled_at__isnull=False)
        .values_list("eve_fleet_id", flat=True)
        .distinct()
    )


def ended_at(fleet) -> datetime | None:
    ends = list(_instances(fleet).values_list("end_time", flat=True))
    if not ends or any(end is None for end in ends):
        return None
    return max(ends)


def feed_behind_since(now: datetime | None = None) -> str | None:
    """When the killmail feed last reached zKill, if that was a while ago."""
    now = now or timezone.now()
    cursor = FeedR2z2Cursor.objects.filter(pk=1).first()
    if cursor is None or cursor.last_request_at is None:
        return None
    paused = cursor.paused_until is not None and cursor.paused_until > now
    if paused or now - cursor.last_request_at > FEED_BEHIND_AFTER:
        return cursor.last_request_at.isoformat()
    return None


# ------------------------------------------------------------------ sweep


def _zkill_entity_path(group_id: int) -> str:
    kind = "allianceID" if group_id >= FIRST_ALLIANCE_ID else "corporationID"
    return f"{kind}/{group_id}"


def _sweep_entry(entry: dict, start: datetime) -> str:
    killmail_id = entry.get("killmail_id")
    zkb = entry.get("zkb") or {}
    killmail_hash = zkb.get("hash")
    if not killmail_id or not killmail_hash:
        return "skipped"
    existing = FeedKillmail.objects.filter(killmail_id=killmail_id).first()
    if existing is not None:
        meta = existing.zkb_meta or {}
        if "totalValue" not in meta and "totalValue" in zkb:
            # Mails fetched from ESI carry no price until zKill has one.
            existing.zkb_meta = {**meta, **zkb}
            existing.save(update_fields=["zkb_meta"])
            return "repriced"
        return "known"
    raw = entry if entry.get("victim") and entry.get("attackers") else None
    if raw is None:
        raw = fetch_esi_killmail(killmail_id, killmail_hash)
    if raw is None:
        return "skipped"
    moment = parse_time(raw["killmail_time"].replace("Z", "+00:00"))
    if moment < start:
        return "older"
    stored = upsert_feed_killmail_from_raw(raw, zkb_meta=zkb, source="sweep")
    return "added" if stored else "skipped"


def sweep(fleet, *, now: datetime | None = None) -> dict:
    """Ask zKill for our groups' recent mails and keep any the feed missed."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetFightTimeline

    now = now or timezone.now()
    timeline = EveFleetFightTimeline.objects.filter(eve_fleet=fleet).first()
    start, _ = _bounds(timeline.events if timeline else [])
    stats = {"added": 0, "repriced": 0, "pages": 0, "errors": 0}
    if timeline is None or start is None:
        return stats
    past = math.ceil(
        ((now - start) + timedelta(hours=1)).total_seconds() / 3600
    )
    past_seconds = min(ZKILL_MAX_PAST_SECONDS, past * 3600)
    for group_id in (timeline.names.get("our_groups") or [])[:SWEEP_GROUPS]:
        for page in range(1, SWEEP_MAX_PAGES + 1):
            url = (
                f"{ZKILL_API_BASE}/{_zkill_entity_path(group_id)}"
                f"/pastSeconds/{past_seconds}/page/{page}/"
            )
            try:
                response = zkill_get(url)
                response.raise_for_status()
                entries = response.json()
            except (requests.RequestException, ValueError):
                logger.warning("zKill sweep failed: %s", url)
                stats["errors"] += 1
                break
            stats["pages"] += 1
            if not isinstance(entries, list) or not entries:
                break
            outcomes = [_sweep_entry(entry, start) for entry in entries]
            stats["added"] += outcomes.count("added")
            stats["repriced"] += outcomes.count("repriced")
            time.sleep(SWEEP_SLEEP_SECONDS)
            if "older" in outcomes:
                break
    EveFleetFightTimeline.objects.filter(pk=timeline.pk).update(swept_at=now)
    return stats


# ----------------------------------------------------------------- settle


def lookup_evekill_battles(timeline) -> dict:
    """eve-kill's battle id for each round, found from one of its mails."""
    links = dict(timeline.battle_links or {})
    for summary in (timeline.payload or {}).get("rounds") or []:
        if summary["kind"] != "round":
            continue
        ids = [row["killmail_id"] for row in summary["biggest"]]
        if any(str(killmail_id) in links for killmail_id in ids):
            continue
        killmail_id = ids[0]
        try:
            response = requests.get(
                EVEKILL_BATTLE_URL.format(killmail_id=killmail_id),
                headers=headers(),
                timeout=10,
            )
            battle = response.json().get("battle_id") if response.ok else None
        except (requests.RequestException, ValueError):
            logger.warning("eve-kill battle lookup failed for %s", killmail_id)
            continue
        if battle:
            links[str(killmail_id)] = battle
    return links


def settle(fleet, *, now: datetime | None = None):
    now = now or timezone.now()
    timeline = rebuild(fleet, now=now)
    timeline.battle_links = lookup_evekill_battles(timeline)
    timeline.settled_at = now
    recut(timeline, now=now, save=False)
    timeline.save(update_fields=["battle_links", "settled_at", "payload"])
    return timeline


def next_step(fleet, timeline, now: datetime) -> str | None:
    """What the tick should do after rebuilding: sweep, settle, or nothing."""
    end = ended_at(fleet)
    if end is None or timeline is None:
        return None
    if timeline.swept_at is None and now >= end + SWEEP_AFTER:
        return "sweep"
    if timeline.settled_at is None and now >= end + SETTLE_AFTER:
        return "settle"
    return None


# ------------------------------------------------------------------ edits


@transaction.atomic
def merge(fleet, start: datetime, end: datetime, user):
    """Merge every round between ``start`` and ``end`` into one."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetFightEdit

    # A merge over a split the FC made earlier replaces it.
    EveFleetFightEdit.objects.filter(
        eve_fleet=fleet,
        kind=EveFleetFightEdit.Kind.SPLIT,
        start__gt=start,
        start__lte=end,
    ).delete()
    EveFleetFightEdit.objects.create(
        eve_fleet=fleet,
        kind=EveFleetFightEdit.Kind.MERGE,
        start=start,
        end=end,
        created_by=user,
    )


@transaction.atomic
def split(fleet, at: datetime, user):
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetFightEdit

    EveFleetFightEdit.objects.get_or_create(
        eve_fleet=fleet,
        kind=EveFleetFightEdit.Kind.SPLIT,
        start=at,
        defaults={"created_by": user},
    )


def undo(fleet, edit_id: int | None) -> int:
    """Remove one edit, or every edit when ``edit_id`` is None."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetFightEdit

    edits = EveFleetFightEdit.objects.filter(eve_fleet=fleet)
    if edit_id is not None:
        edits = edits.filter(id=edit_id)
    deleted, _ = edits.delete()
    return deleted


def recut_fleet(fleet):
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetFightTimeline

    timeline = EveFleetFightTimeline.objects.filter(eve_fleet=fleet).first()
    if timeline is None:
        return None
    return recut(timeline)
