"""Manage the external NPSI calendar sources from the site.

A source is a feed the bot imports into the fleet schedule. Sources are
disabled, never deleted, so their imported events keep their history.
"""

from datetime import datetime
from typing import Optional

from django.utils import timezone
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveCharacter
from fleets.helpers.npsi_ingest import (
    FEED_TIMEOUT_SECONDS,
    feed_error_kind,
    public_feed_url,
    try_feed,
)
from fleets.models import EveFleetAudience, NpsiEventSource, NpsiExternalEvent
from groups.helpers.feature_access import can_use_feature

FEATURE = "fleets.npsi_sources.manage"
FORBIDDEN = "You can't manage NPSI event sources."
PREVIEW_LIMIT = 25


class NpsiSourceResponse(BaseModel):
    id: int
    name: str
    feed_url: str
    fc_character_name: str
    default_audience_id: Optional[int] = None
    default_audience_name: Optional[str] = None
    enabled: bool
    last_polled_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error: str
    # timeout, unreachable, http, not_json, not_list, not_public, other;
    # empty when the last poll worked.
    last_error_kind: str = ""
    event_count: int
    upcoming_count: int = 0
    fc_character_id: Optional[int] = None


class NpsiAudienceOption(BaseModel):
    id: int
    name: str


class NpsiSourceList(BaseModel):
    sources: list[NpsiSourceResponse]
    audiences: list[NpsiAudienceOption]
    # How long a poll waits for a feed before it gives up.
    feed_timeout_seconds: int = FEED_TIMEOUT_SECONDS


class NpsiSourceCreate(BaseModel):
    name: str
    feed_url: str
    fc_character_name: str
    default_audience_id: Optional[int] = None


class NpsiSourcePatch(BaseModel):
    name: Optional[str] = None
    feed_url: Optional[str] = None
    fc_character_name: Optional[str] = None
    default_audience_id: Optional[int] = None
    enabled: Optional[bool] = None


class NpsiEventPreview(BaseModel):
    id: int
    summary: str
    start_time: datetime
    end_time: Optional[datetime] = None
    character_name: str
    status: str
    skip_reason: str


class NpsiTryEvent(BaseModel):
    summary: str
    start_time: datetime
    character_name: str


class NpsiTryResult(BaseModel):
    """A dry-run read of a feed: nothing stored, nothing sent."""

    ok: bool
    error: str
    error_kind: str
    item_count: int
    upcoming_count: int
    upcoming: list[NpsiTryEvent]
    feed_timeout_seconds: int = FEED_TIMEOUT_SECONDS


def _fc_character_ids(names) -> dict[str, int]:
    return dict(
        EveCharacter.objects.filter(character_name__in=set(names)).values_list(
            "character_name", "character_id"
        )
    )


def _source_row(source: NpsiEventSource, fc_ids=None) -> dict:
    audience = source.default_audience
    if fc_ids is None:
        fc_ids = _fc_character_ids([source.fc_character_name])
    return {
        "id": source.id,
        "name": source.name,
        "feed_url": source.feed_url,
        "fc_character_name": source.fc_character_name,
        "default_audience_id": audience.id if audience else None,
        "default_audience_name": audience.name if audience else None,
        "enabled": source.enabled,
        "last_polled_at": source.last_polled_at,
        "last_success_at": source.last_success_at,
        "last_error": source.last_error,
        "last_error_kind": feed_error_kind(source.last_error),
        "event_count": source.events.count(),
        "upcoming_count": source.events.filter(
            start_time__gte=timezone.now()
        ).count(),
        "fc_character_id": fc_ids.get(source.fc_character_name),
    }


def _valid_url(url: str) -> bool:
    return public_feed_url(url)


def _denied(request):
    if can_use_feature(request.user, FEATURE):
        return None
    return 403, ErrorResponse(detail=FORBIDDEN)


def _audience_error(audience_id):
    if (
        audience_id
        and not EveFleetAudience.objects.filter(pk=audience_id).exists()
    ):
        return "That audience does not exist."
    return None


LIST_PATH = "/npsi-sources"
LIST_METHOD = "get"
LIST_SPEC = {
    "summary": "NPSI event sources, with the last import time and errors",
    "auth": AuthBearer(),
    "response": {200: NpsiSourceList, 403: ErrorResponse},
}


def get_npsi_sources(request):
    if (denied := _denied(request)) is not None:
        return denied
    sources = NpsiEventSource.objects.select_related(
        "default_audience"
    ).order_by("name")
    fc_ids = _fc_character_ids(source.fc_character_name for source in sources)
    return 200, {
        "sources": [_source_row(source, fc_ids) for source in sources],
        "audiences": [
            {"id": audience.id, "name": audience.name}
            for audience in EveFleetAudience.objects.order_by("name")
        ],
    }


CREATE_PATH = "/npsi-sources"
CREATE_METHOD = "post"
CREATE_SPEC = {
    "summary": "Add an NPSI event source",
    "auth": AuthBearer(),
    "response": {
        200: NpsiSourceResponse,
        400: ErrorResponse,
        403: ErrorResponse,
    },
}


def post_npsi_source(request, payload: NpsiSourceCreate):
    if (denied := _denied(request)) is not None:
        return denied
    name = payload.name.strip()
    fc_name = payload.fc_character_name.strip()
    feed_url = payload.feed_url.strip()
    if not name or not fc_name:
        return 400, ErrorResponse(detail="Name and fallback FC are required.")
    if not _valid_url(feed_url):
        return 400, ErrorResponse(detail="Enter a public http(s) feed URL.")
    if NpsiEventSource.objects.filter(name=name).exists():
        return 400, ErrorResponse(detail="A source with that name exists.")
    if error := _audience_error(payload.default_audience_id):
        return 400, ErrorResponse(detail=error)
    source = NpsiEventSource.objects.create(
        name=name,
        feed_url=feed_url,
        fc_character_name=fc_name,
        default_audience_id=payload.default_audience_id,
    )
    return 200, _source_row(source)


PATCH_PATH = "/npsi-sources/{source_id}"
PATCH_METHOD = "patch"
PATCH_SPEC = {
    "summary": "Edit, enable or disable an NPSI event source",
    "auth": AuthBearer(),
    "response": {
        200: NpsiSourceResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def patch_npsi_source(request, source_id: int, payload: NpsiSourcePatch):
    if (denied := _denied(request)) is not None:
        return denied
    source = (
        NpsiEventSource.objects.select_related("default_audience")
        .filter(pk=source_id)
        .first()
    )
    if source is None:
        return 404, ErrorResponse(detail="Source not found.")
    changes = payload.dict(exclude_unset=True)
    for field in ("name", "feed_url", "fc_character_name"):
        if field in changes:
            changes[field] = (changes[field] or "").strip()
            if not changes[field]:
                return 400, ErrorResponse(detail=f"{field} cannot be empty.")
    if "feed_url" in changes and not _valid_url(changes["feed_url"]):
        return 400, ErrorResponse(detail="Enter a public http(s) feed URL.")
    if (
        "name" in changes
        and NpsiEventSource.objects.filter(name=changes["name"])
        .exclude(pk=source.pk)
        .exists()
    ):
        return 400, ErrorResponse(detail="A source with that name exists.")
    if error := _audience_error(changes.get("default_audience_id")):
        return 400, ErrorResponse(detail=error)
    if changes.get("enabled") is None:
        changes.pop("enabled", None)
    for field, value in changes.items():
        setattr(source, field, value)
    source.save()
    source.refresh_from_db()
    return 200, _source_row(source)


EVENTS_PATH = "/npsi-sources/{source_id}/events"
EVENTS_METHOD = "get"
EVENTS_SPEC = {
    "summary": "Preview a source's upcoming imported events",
    "auth": AuthBearer(),
    "response": {
        200: list[NpsiEventPreview],
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def get_npsi_source_events(request, source_id: int):
    if (denied := _denied(request)) is not None:
        return denied
    if not NpsiEventSource.objects.filter(pk=source_id).exists():
        return 404, ErrorResponse(detail="Source not found.")
    events = NpsiExternalEvent.objects.filter(
        source_id=source_id, start_time__gte=timezone.now()
    ).order_by("start_time")[:PREVIEW_LIMIT]
    return 200, [
        {
            "id": event.id,
            "summary": event.summary,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "character_name": event.character_name,
            "status": event.status,
            "skip_reason": event.skip_reason,
        }
        for event in events
    ]


TRY_PATH = "/npsi-sources/{source_id}/try"
TRY_METHOD = "post"
TRY_SPEC = {
    "summary": "Read a source's feed now, without importing or posting",
    "auth": AuthBearer(),
    "response": {
        200: NpsiTryResult,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_npsi_source_try(request, source_id: int):
    """A dry run: fetch and parse the saved feed address, store nothing.

    The source's last import columns stay as the scheduled poll left them,
    and no event is created or sent to Discord.
    """
    if (denied := _denied(request)) is not None:
        return denied
    source = NpsiEventSource.objects.filter(pk=source_id).first()
    if source is None:
        return 404, ErrorResponse(detail="Source not found.")
    return 200, try_feed(source)
