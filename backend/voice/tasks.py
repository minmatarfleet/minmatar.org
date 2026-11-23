"""Voice tasks, on the ``voice`` queue.

The 30-second fleet poll does no voice work itself: it queues
``sync_fleet_grants`` for Mumble fleets only.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta

import sentry_sdk
from django.utils import timezone

from app.celery import app
from fleets.models import EveFleet, EveFleetInstance
from voice import grants, leases, publisher, store
from voice.models import VoiceChannelLease, VoiceGrant, VoiceIdentity

logger = logging.getLogger(__name__)

HEARTBEAT_MAX_AGE = timedelta(seconds=60)


def _republish_after_lease_change() -> None:
    # Standing commanders and capital pilots gain or lose a whole branch,
    # so a lease change republishes every identity, not just the grants.
    publisher.publish_leases()
    publisher.publish_characters(
        VoiceIdentity.objects.values_list("character_id", flat=True)
    )


@app.task(expires=60)
def sync_fleet_grants(instance_id: int):
    """After a fleet poll: refresh a Mumble fleet's grants and lease."""
    instance = (
        EveFleetInstance.objects.filter(id=instance_id)
        .select_related("eve_fleet__voice_option")
        .first()
    )
    if instance is None or not instance.eve_fleet.uses_mumble:
        return
    sync_fleet(instance.eve_fleet)


def sync_fleet(fleet: EveFleet) -> None:
    lease = VoiceChannelLease.active().filter(fleet=fleet).first()
    if lease is None and leases.wants_lease(fleet):
        lease = leases.acquire(fleet)
        if lease is not None:
            grants.sync_fleet(fleet)
            _republish_after_lease_change()
            return
    if lease is None:
        return
    changed = grants.sync_fleet(fleet)
    if changed:
        publisher.publish_characters(changed)


@app.task(expires=60, exclusive=2 * 60)
def expire_grants():
    """Every minute: end and start leases, refresh leased fleets' grants."""
    result = leases.maintain()
    if result["released"] or result["acquired"]:
        for fleet_id in result["acquired"]:
            grants.sync_fleet(EveFleet.objects.get(id=fleet_id))
        _republish_after_lease_change()
    for lease in VoiceChannelLease.active().select_related("fleet"):
        if lease.fleet_id in result["acquired"]:
            continue
        changed = grants.sync_fleet(lease.fleet)
        if changed:
            publisher.publish_characters(changed)
    if publisher.records_missing():
        logger.warning("Voice records missing from Redis: rebuilding")
        publisher.rebuild_all()


@app.task(expires=60 * 60)
def rebuild_records():
    """Hourly: republish everything, so drift never lasts."""
    return publisher.rebuild_all()


@app.task(expires=5 * 60)
def publish_fleet_wing_pilots(fleet_id: int):
    """The FC changed the wing map: republish this fleet's pilots who have
    a wing (nobody else's placement can change)."""
    publisher.publish_characters(
        VoiceGrant.objects.filter(
            fleet_id=fleet_id,
            expires_at__isnull=True,
            wing_id__isnull=False,
        )
        .values_list("character_id", flat=True)
        .distinct()
    )


@app.task(expires=60)
def publish_character_task(character_id: int):
    publisher.publish_character(character_id)


@app.task(expires=60)
def publish_user_characters(user_id: int):
    # pylint: disable=import-outside-toplevel
    from eveonline.models import EveCharacter

    publisher.publish_characters(
        EveCharacter.objects.filter(user_id=user_id).values_list(
            "character_id", flat=True
        )
    )


def heartbeat_problem(raw, now=None) -> str | None:
    """Why the voice service looks unhealthy, or None."""
    now = now or timezone.now()
    if raw is None:
        return "no heartbeat"
    try:
        beat = json.loads(raw)
        at = timezone.datetime.fromisoformat(beat["at"])
    except (ValueError, KeyError, TypeError):
        return "unreadable heartbeat"
    if now - at > HEARTBEAT_MAX_AGE:
        return f"heartbeat {int((now - at).total_seconds())}s old"
    if not beat.get("authenticator"):
        return "authenticator not registered"
    return None


@app.task(expires=60)
def heartbeat_check():
    """Raise a Sentry error when the voice service stops reporting.

    Quiet until the Mumble option is switched on: before go-live there is
    no voice service to report.
    """
    # pylint: disable=import-outside-toplevel
    from fleets.models import FleetVoiceOption

    if not FleetVoiceOption.objects.filter(
        kind=FleetVoiceOption.KIND_MUMBLE, is_active=True
    ).exists():
        return None
    problem = heartbeat_problem(store.get_client().get(store.HEARTBEAT_KEY))
    if problem:
        sentry_sdk.capture_message(
            f"Voice service unhealthy: {problem}", level="error"
        )
    return problem


@app.task(expires=60)
def sync_fleet_task(fleet_id: int):
    """A signup changed on a leased Mumble fleet."""
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet is not None and fleet.uses_mumble:
        sync_fleet(fleet)


@app.task(expires=60)
def publish_all_identities():
    publisher.publish_characters(
        VoiceIdentity.objects.values_list("character_id", flat=True)
    )
