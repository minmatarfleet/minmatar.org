"""Intel sheet API: share a d-scan or Local, read recent intel and pings.

Used by the desktop app's Intel window and the my.minmatar.org scan page.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache

from django.core.cache import cache
from django.http import HttpResponse
from eveuniverse.models import EveSolarSystem
from ninja import Router, Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.helpers.characters.characters import user_primary_character
from eveonline.models import EveCharacter
from groups.helpers.feature_access import can_use_feature
from intel.models import IntelReport
from intel.services.fixtures import load_map, system_ids_by_name
from intel.services.local import HOSTILE, summarize_local
from intel.services.paste import DSCAN, LOCAL, PasteError, parse
from intel.services.recent import (
    RECENT_MINUTES,
    invalidate_recent,
    recent_intel,
    report_summary_line,
)
from intel.services.ships import summarize_dscan

router = Router(tags=["Intel"])

VIEW_FEATURE = "intel.view"
REPORT_FEATURE = "intel.report"
REPORTS_PER_WINDOW = 30
REPORT_WINDOW_SECONDS = 300


class PasteRequest(Schema):
    text: str
    kind: str | None = None


class CreateReportRequest(PasteRequest):
    system: str
    note: str = ""
    # Which of your characters is reporting (the one whose client is in
    # front); anything else falls back to your primary character.
    character_name: str | None = None


class PreviewResponse(Schema):
    kind: str
    lines: int
    summary: dict


class ShipSchema(Schema):
    type_id: int
    name: str
    count: int


class ImageSchema(Schema):
    kind: str
    id: int


class RecentItemSchema(Schema):
    id: str
    kind: str
    is_ping: bool
    report_id: str | None
    system_id: int | None
    system_name: str
    occurred_at: datetime
    source: str
    note: str
    count: int | None
    summary: str
    image: ImageSchema | None
    ships: list[ShipSchema]
    standings: dict | None


class RecentResponse(Schema):
    items: list[RecentItemSchema]
    window_minutes: int
    generated_at: datetime


class PreviousLocalSchema(Schema):
    report_id: str
    created_at: datetime
    hostile: int
    hostile_delta: int


class ReportResponse(Schema):
    report_id: str
    kind: str
    system_id: int | None
    system_name: str
    reporter_name: str
    note: str
    created_at: datetime
    summary_line: str
    summary: dict
    raw: str
    previous: PreviousLocalSchema | None = None


def _resolve_system(name: str) -> tuple[int, str] | None:
    name = " ".join((name or "").split())
    if not name:
        return None
    system_id = system_ids_by_name().get(name.lower())
    if system_id:
        return system_id, load_map()["systems"][str(system_id)]
    row = (
        EveSolarSystem.objects.filter(name__iexact=name)
        .values_list("id", "name")
        .first()
    )
    return (int(row[0]), row[1]) if row else None


def _reporter_name(user, character_name: str | None) -> str:
    if character_name:
        own = (
            EveCharacter.objects.filter(
                user=user, character_name__iexact=character_name.strip()
            )
            .values_list("character_name", flat=True)
            .first()
        )
        if own:
            return own
    primary = user_primary_character(user)
    return primary.character_name if primary else user.username


def _rate_limited(user) -> bool:
    key = f"intel:reports:{user.pk}"
    added = cache.add(key, 1, REPORT_WINDOW_SECONDS)
    if added:
        return False
    try:
        return cache.incr(key) > REPORTS_PER_WINDOW
    except ValueError:
        return False


def _summarize(kind: str, entries: list, *, resolve_local: bool) -> dict:
    if kind == DSCAN:
        return summarize_dscan(entries)
    if resolve_local:
        return summarize_local(entries)
    return {"pilots": len(entries), "resolved": False}


def _previous_local(report: IntelReport) -> PreviousLocalSchema | None:
    if report.kind != LOCAL or not report.solar_system_id:
        return None
    previous = (
        IntelReport.objects.filter(
            kind=LOCAL,
            solar_system_id=report.solar_system_id,
            created_at__lt=report.created_at,
            created_at__gte=report.created_at
            - timedelta(minutes=RECENT_MINUTES),
        )
        .only("public_id", "created_at", "summary")
        .order_by("-created_at")
        .first()
    )
    if previous is None or not (previous.summary or {}).get("resolved"):
        return None
    if not (report.summary or {}).get("resolved"):
        return None
    hostile = report.summary["standings"][HOSTILE]
    before = previous.summary["standings"][HOSTILE]
    return PreviousLocalSchema(
        report_id=previous.public_id,
        created_at=previous.created_at,
        hostile=before,
        hostile_delta=hostile - before,
    )


def _report_response(report: IntelReport) -> ReportResponse:
    return ReportResponse(
        report_id=report.public_id,
        kind=report.kind,
        system_id=report.solar_system_id,
        system_name=report.system_name,
        reporter_name=report.reporter_name,
        note=report.note,
        created_at=report.created_at,
        summary_line=report_summary_line(report),
        summary=report.summary or {},
        raw=report.raw,
        previous=_previous_local(report),
    )


@router.post(
    "/reports/preview",
    summary="Parse a d-scan or Local paste without sharing it",
    auth=AuthBearer(),
    response={200: PreviewResponse, 400: ErrorResponse, 403: ErrorResponse},
)
def preview_report(request, payload: PasteRequest):
    if not can_use_feature(request.user, REPORT_FEATURE):
        return 403, ErrorResponse(detail="You can't share intel.")
    try:
        kind, entries = parse(payload.text, payload.kind)
    except PasteError as err:
        return 400, ErrorResponse(detail=str(err))
    return PreviewResponse(
        kind=kind,
        lines=len(entries),
        summary=_summarize(kind, entries, resolve_local=False),
    )


@router.post(
    "/reports",
    summary="Share a d-scan or Local paste to the intel sheet",
    auth=AuthBearer(),
    response={
        200: ReportResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        429: ErrorResponse,
    },
)
def create_report(request, payload: CreateReportRequest):
    if not can_use_feature(request.user, REPORT_FEATURE):
        return 403, ErrorResponse(detail="You can't share intel.")
    try:
        kind, entries = parse(payload.text, payload.kind)
    except PasteError as err:
        return 400, ErrorResponse(detail=str(err))
    system = _resolve_system(payload.system)
    if system is None:
        return 400, ErrorResponse(detail="Pick the system this is from.")
    if _rate_limited(request.user):
        return 429, ErrorResponse(
            detail="That's a lot of reports. Wait a few minutes."
        )

    report = IntelReport.objects.create(
        kind=kind,
        solar_system_id=system[0],
        system_name=system[1],
        reporter=request.user,
        reporter_name=_reporter_name(request.user, payload.character_name),
        note=" ".join(payload.note.split())[:200],
        raw=payload.text,
        summary=_summarize(kind, entries, resolve_local=True),
    )
    invalidate_recent()
    return _report_response(report)


@router.get(
    "/reports/{report_id}",
    summary="One shared d-scan or Local report",
    auth=AuthBearer(),
    response={200: ReportResponse, 403: ErrorResponse, 404: ErrorResponse},
)
def get_report(request, report_id: str):
    if not can_use_feature(request.user, VIEW_FEATURE):
        return 403, ErrorResponse(detail="You can't view intel.")
    report = IntelReport.objects.filter(public_id=report_id).first()
    if report is None:
        return 404, ErrorResponse(detail="No such report.")
    return _report_response(report)


@router.get(
    "/recent",
    summary="Intel reports and capital / fleet pings from the last 2 hours",
    auth=AuthBearer(),
    response={200: RecentResponse, 403: ErrorResponse},
)
def get_recent(request):
    if not can_use_feature(request.user, VIEW_FEATURE):
        return 403, ErrorResponse(detail="You can't view intel.")
    return recent_intel()


@lru_cache(maxsize=1)
def _map_body() -> bytes:
    data = load_map()
    return json.dumps(
        {
            "source": data.get("source"),
            "systems": data.get("systems", {}),
            "edges": data.get("edges", {}),
        },
        separators=(",", ":"),
    ).encode()


@router.get(
    "/map",
    summary="Gate graph the desktop app uses to count jumps locally",
    description=(
        "SDE data only. The app works out jumps from the pilot's own "
        "system itself, so their location never leaves their PC."
    ),
)
def get_map(request):
    response = HttpResponse(_map_body(), content_type="application/json")
    response["Cache-Control"] = "public, max-age=86400"
    return response
