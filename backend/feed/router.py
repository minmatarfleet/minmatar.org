from __future__ import annotations

from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone
from ninja import Router, Schema

from feed.constants import (
    FEED_DEFAULT_HISTORY_DAYS,
    FEED_DEFAULT_PAGE_LIMIT,
    FEED_MAX_HISTORY_DAYS,
)
from feed.helpers.warzone_briefing import (
    WarzoneSystemRow,
    build_warzone_briefing,
)
from feed.models import FeedEvent

router = Router(tags=["Feed"])


class FeedEventItemSchema(Schema):
    id: str
    kind: str
    occurred_at: datetime
    title: str
    subheader: str
    preview: str
    body: str
    accent: str
    payload: dict


class FeedListResponse(Schema):
    items: list[FeedEventItemSchema]
    next_cursor: str | None = None


class WarzoneSystemSchema(Schema):
    system_id: int
    system_name: str
    sun_type_id: int
    contested_percent: float
    delta_24h: float
    kills_24h: int
    front: str
    occupier: str | None


class WarzoneBriefingResponse(Schema):
    hot_kills: WarzoneSystemSchema | None
    amarr_contested: list[WarzoneSystemSchema]
    minmatar_contested: list[WarzoneSystemSchema]
    changes_24h: list[WarzoneSystemSchema]
    updated_at: datetime | None
    has_full_24h_window: bool


def _warzone_system_schema(row: WarzoneSystemRow) -> WarzoneSystemSchema:
    return WarzoneSystemSchema(
        system_id=row.system_id,
        system_name=row.system_name,
        sun_type_id=row.sun_type_id,
        contested_percent=row.contested_percent,
        delta_24h=row.delta_24h,
        kills_24h=row.kills_24h,
        front=row.front,
        occupier=row.occupier,
    )


def _parse_cursor(cursor: str | None) -> tuple[datetime | None, int | None]:
    if not cursor:
        return None, None
    parts = cursor.split(":", 1)
    if len(parts) != 2:
        return None, None
    try:
        occurred_at = datetime.fromisoformat(parts[0].replace("Z", "+00:00"))
        event_id = int(parts[1])
        return occurred_at, event_id
    except (ValueError, TypeError):
        return None, None


def _encode_cursor(event: FeedEvent) -> str:
    ts = event.occurred_at.isoformat().replace("+00:00", "Z")
    return f"{ts}:{event.id}"


@router.get("/", response=FeedListResponse)
def list_feed(
    request,
    cursor: str | None = None,
    limit: int = FEED_DEFAULT_PAGE_LIMIT,
    days: int = FEED_DEFAULT_HISTORY_DAYS,
):
    days = max(1, min(days, FEED_MAX_HISTORY_DAYS))
    limit = max(1, min(limit, 100))
    now = timezone.now()
    window_start = now - timedelta(days=days)

    qs = (
        FeedEvent.objects.filter(occurred_at__gte=window_start)
        .exclude(kind="militia_joins")
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
    )

    cursor_time, cursor_id = _parse_cursor(cursor)
    if cursor_time and cursor_id:
        qs = qs.filter(
            Q(occurred_at__lt=cursor_time)
            | Q(occurred_at=cursor_time, id__lt=cursor_id)
        )

    events = list(qs.order_by("-occurred_at", "-id")[: limit + 1])
    has_more = len(events) > limit
    if has_more:
        events = events[:limit]

    items = [
        FeedEventItemSchema(
            id=str(event.id),
            kind=event.kind,
            occurred_at=event.occurred_at,
            title=event.title,
            subheader=event.subheader,
            preview=event.preview,
            body=event.body,
            accent=event.accent,
            payload=event.payload,
        )
        for event in events
    ]
    next_cursor = _encode_cursor(events[-1]) if has_more and events else None
    return FeedListResponse(items=items, next_cursor=next_cursor)


@router.get("/warzone", response=WarzoneBriefingResponse)
def warzone_briefing(request):
    briefing = build_warzone_briefing()
    return WarzoneBriefingResponse(
        hot_kills=(
            _warzone_system_schema(briefing.hot_kills)
            if briefing.hot_kills
            else None
        ),
        amarr_contested=[
            _warzone_system_schema(row) for row in briefing.amarr_contested
        ],
        minmatar_contested=[
            _warzone_system_schema(row) for row in briefing.minmatar_contested
        ],
        changes_24h=[
            _warzone_system_schema(row) for row in briefing.changes_24h
        ],
        updated_at=briefing.updated_at,
        has_full_24h_window=briefing.has_full_24h_window,
    )
