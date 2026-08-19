"""Discord button payloads for NPSI ingest DMs."""

from __future__ import annotations

from datetime import datetime

from django.conf import settings

from fleets.models import NpsiExternalEvent

POST_CUSTOM_ID_PREFIX = "npsi:create:"
PREPING_CUSTOM_ID_PREFIX = "npsi:preping:"
TRACK_CUSTOM_ID_PREFIX = "npsi:track:"


def post_custom_id(event_id: int) -> str:
    return f"{POST_CUSTOM_ID_PREFIX}{int(event_id)}"


def preping_custom_id(event_id: int) -> str:
    return f"{PREPING_CUSTOM_ID_PREFIX}{int(event_id)}"


def track_custom_id(event_id: int) -> str:
    return f"{TRACK_CUSTOM_ID_PREFIX}{int(event_id)}"


def _unix(dt: datetime) -> int:
    return int(dt.timestamp())


def _fleet_url(fleet_id: int) -> str:
    base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org")
    return f"{base.rstrip('/')}/fleets/upcoming/"


def npsi_event_embed(event: NpsiExternalEvent) -> dict:
    start = event.start_time
    description = (event.description or "")[:4096]
    fields = [
        {
            "name": "FC",
            "value": event.character_name or event.source.fc_character_name,
            "inline": True,
        },
        {
            "name": "Formup",
            "value": event.location_text or "Ask FC",
            "inline": True,
        },
    ]
    if start:
        fields.append(
            {
                "name": "Start",
                "value": f"<t:{_unix(start)}:F> (<t:{_unix(start)}:R>)",
                "inline": False,
            }
        )
    return {
        "title": event.summary or "NPSI fleet",
        "description": description,
        "fields": fields,
        "footer": {"text": event.source.name},
    }


def post_to_schedule_components(event_id: int) -> list[dict]:
    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 1,
                    "label": "Post to schedule",
                    "custom_id": post_custom_id(event_id),
                }
            ],
        }
    ]


def posted_fleet_components(event: NpsiExternalEvent) -> list[dict]:
    buttons = [
        {
            "type": 2,
            "style": 2,
            "label": "Pre-ping",
            "custom_id": preping_custom_id(event.id),
        },
        {
            "type": 2,
            "style": 3,
            "label": "Track",
            "custom_id": track_custom_id(event.id),
        },
    ]
    if event.eve_fleet_id:
        buttons.append(
            {
                "type": 2,
                "style": 5,
                "label": "Open schedule",
                "url": _fleet_url(event.eve_fleet_id),
            }
        )
    return [{"type": 1, "components": buttons}]


def notify_dm_payload(event: NpsiExternalEvent) -> dict:
    return {
        "content": (
            f"New **{event.source.name}** event. "
            "Post it to the Minmatar fleet schedule?"
        ),
        "embeds": [npsi_event_embed(event)],
        "components": post_to_schedule_components(event.id),
    }


def posted_dm_payload(event: NpsiExternalEvent) -> dict:
    fleet_id = event.eve_fleet_id
    content = (
        f"Posted **{event.summary}** to the fleet schedule "
        f"(#{fleet_id}). Pre-ping when you want pings; Track when you are "
        "in-game fleet boss."
    )
    return {
        "content": content,
        "embeds": [npsi_event_embed(event)],
        "components": posted_fleet_components(event),
    }
