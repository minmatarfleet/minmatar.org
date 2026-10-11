"""Local dev helpers for Unaligned NPSI (no Discord required)."""

from __future__ import annotations

from datetime import timedelta

import requests
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.utils import timezone

from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveCorporation, EveLocation
from fleets.helpers.npsi_actions import NpsiActionError, post_event_to_schedule
from fleets.helpers.npsi_ingest import (
    event_fingerprint,
    parse_feed_datetime,
    resolve_fc_user,
    upsert_feed_item,
)
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    NpsiEventSource,
    NpsiExternalEvent,
)
from groups.helpers.feature_access import can_use_feature

UNALIGNED_FEED_URL = (
    "https://unaligned-event-api-984689261396.europe-west1.run.app/events"
)

SAMPLE_DESCRIPTION_HTML = (
    "Roaming through nullsec and taking fights outnumbered!"
    "<br><br>Doctrine:\xa0"
    '<a href="https://eveworkbench.com/fleet/598638a9-bd3a-4b6c-57bb-08de7d0f3e96"'
    ' target="_blank">https://eveworkbench.com/fleet/598638a9-bd3a-4b6c-57bb-08de7d0f3e96</a>'
    "<br>Discord:\xa0"
    '<a href="https://discord.gg/26QbDN357A" target="_blank">'
    "https://discord.gg/26QbDN357A</a><br>"
    "In game channel: 'Unaligned NPSI'<br>Formup: Jita<br><br>"
    "**FC: Vex Drake**"
)

JITA_LOCATION_ID = 60003760


def ensure_jita_fleets_location() -> EveLocation:
    location, _ = EveLocation.objects.update_or_create(
        location_id=JITA_LOCATION_ID,
        defaults={
            "location_name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            "solar_system_id": 30000142,
            "solar_system_name": "Jita",
            "short_name": "Jita",
            "fleets_active": True,
        },
    )
    if not location.fleets_active:
        location.fleets_active = True
        location.save(update_fields=["fleets_active", "updated_at"])
    return location


def ensure_local_fleet_audience() -> EveFleetAudience:
    audience = EveFleetAudience.objects.filter(hidden=False).first()
    if audience is not None:
        return audience

    staging = EveLocation.objects.filter(staging_active=True).first()
    if staging is None:
        staging = ensure_jita_fleets_location()
        staging.staging_active = True
        staging.save(update_fields=["staging_active", "updated_at"])

    return EveFleetAudience.objects.create(
        name="Local Fleet Audience",
        discord_channel_name="local-fleets",
    )


def ensure_unaligned_source(
    *, audience: EveFleetAudience | None = None
) -> NpsiEventSource:
    jita = ensure_jita_fleets_location()
    if audience is None:
        audience = ensure_local_fleet_audience()

    source, _ = NpsiEventSource.objects.update_or_create(
        name="Unaligned",
        defaults={
            "feed_url": UNALIGNED_FEED_URL,
            "fc_character_name": "Vex Drake",
            "default_type": "npsi",
            "default_audience": audience,
            "default_location": jita,
            "enabled": True,
        },
    )
    changed = False
    if source.default_type != "npsi":
        source.default_type = "npsi"
        changed = True
    if source.default_location_id != jita.location_id:
        source.default_location = jita
        changed = True
    if source.default_audience_id is None:
        source.default_audience = audience
        changed = True
    if changed:
        source.save(
            update_fields=[
                "default_type",
                "default_location",
                "default_audience",
                "updated_at",
            ]
        )
    return source


def ensure_fc_user_for_source(source: NpsiEventSource) -> User:
    character_name = source.fc_character_name
    user = resolve_fc_user(character_name)
    if user is not None and can_use_feature(user, "fleets.create"):
        return user

    capable_user = (
        User.objects.filter(is_superuser=True, is_active=True).first()
        or User.objects.filter(is_staff=True, is_active=True).first()
    )
    if capable_user is None:
        for candidate in User.objects.filter(is_active=True).order_by("id"):
            permission = Permission.objects.filter(
                codename="add_evefleet"
            ).first()
            if permission is not None:
                candidate.user_permissions.add(permission)
            if can_use_feature(candidate, "fleets.create"):
                capable_user = candidate
                break

    if capable_user is None:
        raise ValueError(
            "No site user can create fleets (fleets.create). "
            "Log in via local dev auth or grant fleet create access first."
        )

    corp = EveCorporation.objects.first()
    if corp is None:
        corp = EveCorporation.objects.create(
            corporation_id=987654321,
            name="Local Dev Corp",
        )

    character_id = 900_000_000 + (abs(hash(character_name)) % 99_999_999)
    while EveCharacter.objects.filter(character_id=character_id).exists():
        character_id += 1

    character, created = EveCharacter.objects.get_or_create(
        character_name=character_name,
        defaults={
            "character_id": character_id,
            "user": capable_user,
            "corporation_id": corp.corporation_id,
        },
    )
    if not created and character.user_id != capable_user.id:
        character.user = capable_user
        character.save(update_fields=["user", "updated_at"])
    set_primary_character(capable_user, character)

    if not can_use_feature(capable_user, "fleets.create"):
        raise ValueError(
            f"User {capable_user.username!r} cannot create fleets (fleets.create)."
        )
    return capable_user


def ensure_npsi_source(name: str = "Unaligned") -> NpsiEventSource:
    if name == "Unaligned":
        return ensure_unaligned_source()
    source = NpsiEventSource.objects.filter(name=name).first()
    if source is None:
        raise ValueError(f"Unknown NPSI source {name!r}")
    ensure_jita_fleets_location()
    if source.default_audience_id is None:
        source.default_audience = ensure_local_fleet_audience()
        source.save(update_fields=["default_audience", "updated_at"])
    if source.default_location_id is None:
        source.default_location = ensure_jita_fleets_location()
        source.save(update_fields=["default_location", "updated_at"])
    return source


def bootstrap_local_unaligned_post(
    *,
    source_name: str = "Unaligned",
    from_feed: bool = False,
    summary: str = "Roaming Navies",
    days_ahead: int = 7,
    force: bool = False,
) -> tuple[NpsiExternalEvent, EveFleet]:
    source = ensure_npsi_source(source_name)
    ensure_fc_user_for_source(source)

    if from_feed:
        item = fetch_next_feed_item(source)
    else:
        item = sample_feed_item(source, summary=summary, days_ahead=days_ahead)

    event = upsert_local_event(source, item)
    fleet = post_local_unaligned_event(event, force=force)
    event.refresh_from_db()
    return event, fleet


def sample_feed_item(
    source: NpsiEventSource,
    *,
    summary: str = "Roaming Navies",
    days_ahead: int = 7,
) -> dict:
    start = timezone.now() + timedelta(days=days_ahead)
    end = start + timedelta(hours=3)
    stamp = "%Y-%m-%dT%H:%M:%S.000Z"
    return {
        "summary": summary,
        "description": SAMPLE_DESCRIPTION_HTML,
        "location": "Jita",
        "start": start.strftime(stamp),
        "end": end.strftime(stamp),
        "allDay": False,
        "character_name": source.fc_character_name,
    }


def fetch_next_feed_item(source: NpsiEventSource) -> dict:
    response = requests.get(source.feed_url, timeout=15)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        raise ValueError("Feed returned no events")

    now = timezone.now()
    upcoming = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        start = parse_feed_datetime(item.get("start"))
        if start is None or start < now:
            continue
        upcoming.append((start, item))
    if not upcoming:
        raise ValueError("Feed has no upcoming events")
    upcoming.sort(key=lambda row: row[0])
    return upcoming[0][1]


def upsert_local_event(
    source: NpsiEventSource, item: dict
) -> NpsiExternalEvent:
    now = timezone.now()
    summary = (item.get("summary") or "").strip() or "NPSI fleet"
    start = parse_feed_datetime(item.get("start"))
    if start is None:
        raise ValueError("Feed item has no valid start time")

    fingerprint = event_fingerprint(source.id, start, summary)
    upsert_feed_item(
        source,
        item,
        now=now,
        skip_notify=True,
        include_past=True,
    )
    return NpsiExternalEvent.objects.get(fingerprint=fingerprint)


def post_local_unaligned_event(
    event: NpsiExternalEvent,
    *,
    force: bool = False,
) -> EveFleet:
    if (
        event.status == NpsiExternalEvent.Status.CREATED
        and event.eve_fleet_id
        and not force
    ):
        return event.eve_fleet

    if force and event.eve_fleet_id:
        old_fleet_id = event.eve_fleet_id
        event.eve_fleet = None
        event.status = NpsiExternalEvent.Status.NOTIFIED
        event.save(update_fields=["eve_fleet", "status", "updated_at"])
        EveFleet.objects.filter(id=old_fleet_id).delete()

    try:
        post_event_to_schedule(event)
    except NpsiActionError as exc:
        raise ValueError(str(exc)) from exc

    event.refresh_from_db()
    if event.eve_fleet is None:
        raise ValueError("Post to schedule did not create a fleet")
    return event.eve_fleet


def local_fleet_schedule_url(fleet_id: int) -> str:
    base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org").rstrip(
        "/"
    )
    return f"{base}/fleets/upcoming/{fleet_id}"
