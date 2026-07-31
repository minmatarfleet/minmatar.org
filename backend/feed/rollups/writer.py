from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from feed.helpers.amarr_fleet_pings import maybe_notify_amarr_fleet
from feed.models import (
    FeedEvent,
    FeedEventKillmailLink,
    FeedKillmail,
)
from feed.rollups.config import get_rollup_config
from feed.rollups.types import RollupResult

logger = logging.getLogger(__name__)

FLEET_ACTIVE_ROLLUP = "fleet_active"
# Ordered smallest -> largest; index is used to detect tier upgrades.
_FLEET_TIER_ORDER = ("small", "medium", "large", "heavy", "major")


def write_rollup_results(results: list[RollupResult]) -> int:
    written = 0
    for result in results:
        event = _upsert_event(result)
        _sync_killmail_links(event, result.killmail_ids)
        _maybe_notify_amarr_fleet(event)
        written += 1
    return written


def _maybe_notify_amarr_fleet(event: FeedEvent) -> None:
    if (
        event.rollup_code != FLEET_ACTIVE_ROLLUP
        or event.accent != FeedEvent.Accent.AMARR
    ):
        return
    try:
        maybe_notify_amarr_fleet(event)
    except Exception:
        # Discord failures must not roll back feed event writes.
        logger.exception(
            "Amarr fleet Discord notify failed for event %s", event.pk
        )


def _event_lookup(result: RollupResult) -> dict:
    lookup: dict = {"rollup_code": result.rollup_code}
    if result.cluster_key:
        lookup["cluster_key"] = result.cluster_key
    elif result.source_type and result.source_id is not None:
        lookup["source_type"] = result.source_type
        lookup["source_id"] = result.source_id
    else:
        lookup["cluster_key"] = (
            f"{result.rollup_code}:{result.occurred_at.isoformat()}"
        )
    return lookup


def _event_defaults(result: RollupResult) -> dict:
    return {
        "kind": result.kind,
        "occurred_at": result.occurred_at,
        "title": result.title,
        "subheader": result.subheader,
        "preview": result.preview,
        "body": result.body,
        "payload": result.payload,
        "accent": result.accent,
        "rollup_version": result.rollup_version,
        "is_active": result.is_active,
        "expires_at": result.expires_at,
        "computed_at": timezone.now(),
    }


def _upsert_event(result: RollupResult) -> FeedEvent:
    lookup = _event_lookup(result)
    defaults = _event_defaults(result)

    matches = list(
        FeedEvent.objects.filter(**lookup).order_by("-occurred_at", "-id")
    )
    prior_payloads: list[dict] = []
    if not matches:
        event = FeedEvent.objects.create(**lookup, **defaults)
    else:
        event = matches[0]
        prior_payloads.append(dict(event.payload or {}))
        if len(matches) > 1:
            FeedEvent.objects.filter(
                pk__in=[row.pk for row in matches[1:]]
            ).delete()
        for field, value in defaults.items():
            setattr(event, field, value)
        event.save()

    if result.rollup_code == FLEET_ACTIVE_ROLLUP:
        _coalesce_fleet_active_event(event, result, prior_payloads)
    return event


def _tier_rank(tier: str | None) -> int:
    try:
        return _FLEET_TIER_ORDER.index(tier)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return -1


def _find_fleet_duplicates(
    event: FeedEvent, result: RollupResult
) -> list[FeedEvent]:
    """Other fleet_active events for the same ongoing engagement.

    Matches same system + faction and one of: shared engagement cluster,
    overlapping killmails, or a tip within the stale window of each other.
    """
    payload = event.payload or {}
    system_id = payload.get("system_id")
    faction = payload.get("faction")
    if system_id is None:
        return []

    stale_minutes = get_rollup_config("fleet_active").get("stale_minutes", 20)
    window_seconds = timedelta(minutes=stale_minutes).total_seconds()
    related = payload.get("related_cluster_key")
    event_kms = set(result.killmail_ids or [])

    candidates = FeedEvent.objects.filter(
        rollup_code=FLEET_ACTIVE_ROLLUP
    ).exclude(pk=event.pk)

    duplicates: list[FeedEvent] = []
    for candidate in candidates:
        cp = candidate.payload or {}
        if cp.get("system_id") != system_id or cp.get("faction") != faction:
            continue

        same_engagement = bool(related) and (
            cp.get("related_cluster_key") == related
        )
        close_in_time = (
            abs((candidate.occurred_at - event.occurred_at).total_seconds())
            <= window_seconds
        )
        shares_killmails = False
        if event_kms:
            candidate_kms = set(
                FeedEventKillmailLink.objects.filter(
                    feed_event=candidate
                ).values_list("feed_killmail__killmail_id", flat=True)
            )
            shares_killmails = bool(event_kms & candidate_kms)

        if same_engagement or close_in_time or shares_killmails:
            duplicates.append(candidate)
    return duplicates


def _apply_upgrade_metadata(
    event: FeedEvent, prior_payloads: list[dict]
) -> None:
    """Mark the surviving card when the fight has grown to a larger tier.

    ``upgraded_at`` is sticky: once set it is carried forward on later,
    non-upgrading updates so the UI can keep showing the cue.
    """
    if not prior_payloads:
        return

    payload = dict(event.payload or {})
    new_rank = _tier_rank(payload.get("engagement_tier"))

    top_prior = max(
        prior_payloads,
        key=lambda pp: _tier_rank(pp.get("engagement_tier")),
    )
    top_rank = _tier_rank(top_prior.get("engagement_tier"))

    changed = False
    if new_rank > top_rank >= 0:
        payload["previous_tier"] = top_prior.get("engagement_tier")
        payload["previous_kills"] = top_prior.get("kills")
        payload["previous_pilots"] = top_prior.get("pilots")
        payload["upgraded_at"] = timezone.now().isoformat()
        changed = True
    else:
        # Carry forward an existing upgrade marker from the matched-key prior.
        carry = prior_payloads[0]
        if carry.get("upgraded_at"):
            for field in (
                "previous_tier",
                "previous_kills",
                "previous_pilots",
                "upgraded_at",
            ):
                if carry.get(field) is not None:
                    payload[field] = carry[field]
                    changed = True

    if changed:
        event.payload = payload
        # Concurrent coalesce may delete this row; queryset.update is race-safe.
        FeedEvent.objects.filter(pk=event.pk).update(
            payload=payload,
            updated_at=timezone.now(),
        )


def _coalesce_fleet_active_event(
    event: FeedEvent, result: RollupResult, prior_payloads: list[dict]
) -> None:
    duplicates = _find_fleet_duplicates(event, result)
    prior_payloads = list(prior_payloads) + [
        dict(dup.payload or {}) for dup in duplicates
    ]

    _apply_upgrade_metadata(event, prior_payloads)

    if duplicates:
        FeedEvent.objects.filter(
            pk__in=[dup.pk for dup in duplicates]
        ).delete()


def _sync_killmail_links(event: FeedEvent, killmail_ids: list[int]) -> None:
    if not killmail_ids:
        return
    existing = set(
        FeedEventKillmailLink.objects.filter(feed_event=event).values_list(
            "feed_killmail_id", flat=True
        )
    )
    killmails = FeedKillmail.objects.filter(killmail_id__in=killmail_ids)
    to_create = [
        FeedEventKillmailLink(feed_event=event, feed_killmail=km)
        for km in killmails
        if km.id not in existing
    ]
    if to_create:
        FeedEventKillmailLink.objects.bulk_create(
            to_create, ignore_conflicts=True
        )
