"""One feed card per tracked fleet, listing what it killed and lost.

The card is live while the fleet instance is open and settles when it ends.
It is keyed by the fleet instance, so each pass rewrites the same event and
the writer links it back to the instance through ``FeedEventFleetLink``.

Campaign standing fleets are left out: they stay open for days and the
campaign already scores their kills.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from feed.helpers.fleet_kills import (
    HEADLINE_LIMIT,
    build_fleet_kills_payload,
    match_fleet_killmails,
    stored_killmail_rows,
)
from feed.models import FeedEvent
from feed.rollups.config import get_rollup_version
from feed.rollups.types import RollupContext, RollupResult

logger = logging.getLogger(__name__)

ROLLUP_CODE = "fleet_kills"

EXCLUDED_FLEET_TYPES = ("standing",)
# zKill can deliver a mail well after the ship died. Past this after the
# fleet ended, the card is settled and later passes leave it alone.
SETTLE_AFTER = timedelta(hours=2)
# The poller touches an open instance every few minutes; past this it has
# stopped, so the card should stop claiming the fleet is out.
LIVE_STALE_AFTER = timedelta(minutes=30)


def format_isk(value: int) -> str:
    for divisor, suffix in ((10**12, "T"), (10**9, "B"), (10**6, "M")):
        if value >= divisor:
            return f"{value / divisor:.1f}{suffix}"
    if value >= 10**3:
        return f"{value / 10**3:.0f}K"
    return str(value)


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def fleet_kills_cluster_key(instance_id: int) -> str:
    return f"{ROLLUP_CODE}:{instance_id}"


def _is_live(instance) -> bool:
    if instance.end_time is not None or instance.last_updated is None:
        return False
    return timezone.now() - instance.last_updated <= LIVE_STALE_AFTER


def build_fleet_kills_result(
    instance, prior: FeedEvent | None = None
) -> RollupResult | None:
    summary = match_fleet_killmails(instance, stored_killmail_rows(prior))
    if not summary.killmails:
        return None

    payload = build_fleet_kills_payload(instance, summary)
    by_id = {row["killmail_id"]: row for row in payload["killmails"]}
    headline = [by_id[killmail_id] for killmail_id in payload["headline"]]

    ships = payload["ships_destroyed"]
    lost = payload["ships_lost"]
    systems = [row["system_name"] for row in payload["systems"]]
    subheader = ", ".join(systems)
    if payload["isk_destroyed"] == 0:
        # Nothing died to the fleet; lead with what it lost, not "0 ISK".
        title = (
            f"Fleet {instance.eve_fleet_id}: lost {_plural(lost, 'ship')}, "
            f"{format_isk(payload['isk_lost'])} ISK"
        )
    else:
        title = (
            f"Fleet {instance.eve_fleet_id}: "
            f"{_plural(ships, 'ship')} destroyed, "
            f"{format_isk(payload['isk_destroyed'])} ISK"
        )
    if lost and payload["isk_destroyed"]:
        subheader = (
            f"{subheader} · lost {_plural(payload['ships_lost'], 'ship')}"
            f" ({format_isk(payload['isk_lost'])})"
        )
    preview = ", ".join(
        f"{row['victim_ship_name'] or 'Unknown'} "
        f"({format_isk(row['isk_value'])})"
        for row in headline[:HEADLINE_LIMIT]
    )

    return RollupResult(
        kind=FeedEvent.Kind.FLEET_KILLS,
        occurred_at=summary.last_killmail_at,
        title=title,
        subheader=subheader,
        preview=preview,
        body=preview,
        accent=FeedEvent.Accent.MILITIA,
        payload=payload,
        rollup_code=ROLLUP_CODE,
        rollup_version=get_rollup_version(ROLLUP_CODE),
        cluster_key=fleet_kills_cluster_key(instance.id),
        is_active=_is_live(instance),
        killmail_ids=[row["killmail_id"] for row in payload["killmails"]],
        fleet_instance_ids=[instance.id],
    )


def _is_settled(instance, prior: FeedEvent | None) -> bool:
    if prior is None or instance.end_time is None:
        return False
    return prior.computed_at >= instance.end_time + SETTLE_AFTER


def run_fleet_kills_rollup(ctx: RollupContext) -> list[RollupResult]:
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstance

    instances = list(
        EveFleetInstance.objects.filter(
            # An open instance stays in while the poller has touched it in
            # the window, so its card is rewritten once more as not live
            # after the poller stops.
            Q(end_time__gte=ctx.since)
            | Q(end_time__isnull=True, last_updated__gte=ctx.since),
            start_time__lte=ctx.until,
        ).exclude(eve_fleet__type__in=EXCLUDED_FLEET_TYPES)
    )
    priors = {
        event.cluster_key: event
        for event in FeedEvent.objects.filter(
            rollup_code=ROLLUP_CODE,
            cluster_key__in=[
                fleet_kills_cluster_key(instance.id) for instance in instances
            ],
        )
    }

    results: list[RollupResult] = []
    for instance in instances:
        prior = priors.get(fleet_kills_cluster_key(instance.id))
        if _is_settled(instance, prior):
            continue
        try:
            result = build_fleet_kills_result(instance, prior)
        except Exception:  # pylint: disable=broad-exception-caught
            # One bad fleet must not cost the feed its other rollups, which
            # are written in the same pass.
            logger.exception(
                "fleet_kills rollup failed for instance %s", instance.id
            )
            continue
        if result is not None:
            results.append(result)
    return results
