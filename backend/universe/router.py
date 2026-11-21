"""/api/universe: structures, the global timerboard and moons.

Visibility is enforced here (universe.access). A structure the caller may
not see answers 404, never 403, so a probe cannot tell it exists.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import List, Literal, Optional

from django.db.models import Prefetch
from django.utils import timezone
from ninja import Router, Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.services.timers import TYPE_NAMES, timer_stage
from eveonline.helpers.characters.identity import primary_refs_for_users
from groups.helpers.feature_access import can_use_feature
from moons.models import EveMoon, EveMoonDistribution, EveMoonScan
from moons.parser import MoonParsingResult, process_moon_paste
from structures.models import EveStructure, EveStructureTimer
from structures.reported import (
    REPORTABLE_TYPES,
    ReportDetails,
    ReportError,
    candidates,
    record_report,
    solar_system_id,
)
from universe.access import (
    can_change_visibility,
    can_see_moon_contents,
    can_see_structure,
    visible_structures,
)

router = Router(tags=["Universe"])

STRUCTURES_FEATURE = "structures.view"
TIMERS_FEATURE = "structures.timers.view"
MOONS_FEATURE = "moons.view"

Visibility = Literal["alliance", "corporation", "private"]


class PilotRef(Schema):
    character_id: Optional[int] = None
    name: str = ""


class UniverseStructure(Schema):
    id: int
    esi_structure_id: Optional[int] = None
    name: str
    type_id: int
    type_name: str
    system_id: int
    system_name: str
    corporation_id: Optional[int] = None
    corporation_name: str = ""
    alliance_name: str = ""
    affiliated_alliance_name: str = ""
    reinforce_hour: Optional[int] = None
    state: str
    state_timer_end: Optional[datetime] = None
    # EFT text a pilot can paste into Pyfa, when the fit is known.
    fitting: Optional[str] = None
    visibility: Visibility
    source: Literal["esi", "reported"]
    reported_by: Optional[PilotRef] = None
    reported_at: Optional[datetime] = None
    last_confirmed_by: Optional[PilotRef] = None
    last_confirmed_at: Optional[datetime] = None
    can_change_visibility: bool = False


class UniverseStructureList(Schema):
    structures: List[UniverseStructure]
    can_report: bool


class StructureMatchRequest(Schema):
    system_name: str
    type_id: int
    name: str = ""


class StructureMatchResponse(Schema):
    system_found: bool
    candidates: List[UniverseStructure]


class StructureReportRequest(Schema):
    # The structure the reporter picked from the candidates, or None for a
    # new one.
    structure_id: Optional[int] = None
    system_name: str
    type_id: int
    name: str = ""
    corporation_name: str = ""
    alliance_name: str = ""
    affiliated_alliance_name: str = ""
    reinforce_hour: Optional[int] = None
    fitting: str = ""


class StructureReportResponse(Schema):
    # The same answer whatever the report touched, so it never reveals a
    # structure the reporter cannot see.
    status: Literal["recorded"]


class VisibilityRequest(Schema):
    visibility: Visibility


class UniverseTimer(Schema):
    id: int
    name: str
    structure_type: str
    type_name: str
    type_id: Optional[int] = None
    system: str
    state: str
    stage: int
    final: bool
    at: datetime
    alliance_name: str = ""
    corporation_name: str = ""
    campaign_name: str = ""
    campaign_slug: str = ""
    done: bool = False


class UniverseTimerList(Schema):
    timers: List[UniverseTimer]
    can_add: bool


class MoonOre(Schema):
    ore: str
    yield_percent: float


class MoonScanRef(Schema):
    reported_at: datetime
    reported_by: Optional[PilotRef] = None
    revenue: Optional[int] = None


class UniverseMoon(Schema):
    id: int
    system: str
    planet: str
    moon: int
    reported_by: Optional[PilotRef] = None
    last_scanned_at: Optional[datetime] = None
    # Null unless the caller may see moon contents.
    rarity: Optional[int] = None
    monthly_revenue: Optional[int] = None
    ores: Optional[List[MoonOre]] = None
    scans: Optional[List[MoonScanRef]] = None


class UniverseMoonList(Schema):
    moons: List[UniverseMoon]
    can_view_contents: bool
    can_report: bool


class MoonReportRequest(Schema):
    paste: str


# Rarity class of each moon ore (R4 ... R64).
ORE_RARITY = {
    "Bitumens": 4,
    "Coesite": 4,
    "Sylvite": 4,
    "Zeolites": 4,
    "Cobaltite": 8,
    "Euxenite": 8,
    "Scheelite": 8,
    "Titanite": 8,
    "Chromite": 16,
    "Otavite": 16,
    "Sperrylite": 16,
    "Vanadinite": 16,
    "Carnotite": 32,
    "Cinnabar": 32,
    "Pollucite": 32,
    "Zircon": 32,
    "Loparite": 64,
    "Monazite": 64,
    "Xenotime": 64,
    "Ytterbite": 64,
}


def _pilot(refs: dict, user_id) -> Optional[PilotRef]:
    if not user_id:
        return None
    ref = refs.get(user_id)
    if not ref:
        return PilotRef()
    return PilotRef(character_id=ref[0], name=ref[1])


def _fitting(structure: EveStructure) -> Optional[str]:
    """EFT text: a report's own paste, or ESI's service list."""
    text = (structure.fitting or "").strip()
    if not text:
        return None
    if structure.source == EveStructure.SOURCE_REPORTED:
        if text.startswith("["):
            return text
        return f"[{structure.type_name}, {structure.name}]\n{text}"
    try:
        services = json.loads(text)
    except ValueError:
        return text
    names = [
        service.get("name", "")
        for service in services
        if isinstance(service, dict) and service.get("name")
    ]
    lines = [f"[{structure.type_name}, {structure.name}]", "", *names]
    return "\n".join(lines)


def _structure(structure: EveStructure, user, refs) -> UniverseStructure:
    corporation = structure.corporation
    alliance = structure.owner_alliance_name
    if not alliance and corporation and corporation.alliance:
        alliance = corporation.alliance.name
    return UniverseStructure(
        id=structure.id,
        esi_structure_id=structure.esi_structure_id,
        name=structure.name,
        type_id=structure.type_id,
        type_name=structure.type_name,
        system_id=structure.system_id,
        system_name=structure.system_name,
        corporation_id=corporation.corporation_id if corporation else None,
        corporation_name=structure.owner_name,
        alliance_name=alliance,
        affiliated_alliance_name=structure.affiliated_alliance_name,
        reinforce_hour=structure.reinforce_hour,
        state=structure.state,
        state_timer_end=structure.state_timer_end,
        fitting=_fitting(structure),
        visibility=structure.visibility,
        source=structure.source,
        reported_by=_pilot(refs, structure.reported_by_id),
        reported_at=structure.reported_at,
        last_confirmed_by=_pilot(refs, structure.last_confirmed_by_id),
        last_confirmed_at=structure.last_confirmed_at,
        can_change_visibility=can_change_visibility(user, structure),
    )


def _serialize(structures, user) -> List[UniverseStructure]:
    rows = list(structures)
    refs = primary_refs_for_users(
        {s.reported_by_id for s in rows if s.reported_by_id}
        | {s.last_confirmed_by_id for s in rows if s.last_confirmed_by_id}
    )
    return [_structure(s, user, refs) for s in rows]


def _visible(user):
    return visible_structures(
        user,
        EveStructure.objects.select_related(
            "corporation", "corporation__alliance"
        ),
    )


@router.get(
    "/structures",
    auth=AuthBearer(),
    response={200: UniverseStructureList, 403: ErrorResponse},
)
def list_structures(request):
    """Every structure the caller may see, soonest timer first."""
    if not can_use_feature(request.user, STRUCTURES_FEATURE):
        return 403, ErrorResponse(detail="You cannot view structures")
    structures = _visible(request.user).order_by("system_name", "name")
    return UniverseStructureList(
        structures=_serialize(structures, request.user),
        can_report=True,
    )


@router.post(
    "/structures/match",
    auth=AuthBearer(),
    response={200: StructureMatchResponse, 403: ErrorResponse},
)
def match_structures(request, payload: StructureMatchRequest):
    """Step one of a report: the structures in that system the reporter
    can see with the same type or a similar name."""
    if not can_use_feature(request.user, STRUCTURES_FEATURE):
        return 403, ErrorResponse(detail="You cannot report structures")
    system_id = solar_system_id(payload.system_name)
    if system_id is None:
        return StructureMatchResponse(system_found=False, candidates=[])
    rows = _visible(request.user).filter(system_id=system_id)
    picked = candidates(
        rows, payload.type_id, payload.name, payload.system_name
    )
    return StructureMatchResponse(
        system_found=True, candidates=_serialize(picked, request.user)
    )


@router.post(
    "/structures/report",
    auth=AuthBearer(),
    response={
        200: StructureReportResponse,
        400: ErrorResponse,
        403: ErrorResponse,
    },
)
def report_structure(request, payload: StructureReportRequest):
    if not can_use_feature(request.user, STRUCTURES_FEATURE):
        return 403, ErrorResponse(detail="You cannot report structures")
    visible = visible_structures(request.user)
    picked = None
    if payload.structure_id is not None:
        picked = visible.filter(id=payload.structure_id).first()
        if picked is None:
            return 400, ErrorResponse(detail="Pick a structure from the list")
    details = ReportDetails(
        system_name=payload.system_name,
        type_id=payload.type_id,
        name=payload.name,
        corporation_name=payload.corporation_name,
        alliance_name=payload.alliance_name,
        affiliated_alliance_name=payload.affiliated_alliance_name,
        reinforce_hour=payload.reinforce_hour,
        fitting=payload.fitting,
    )
    try:
        record_report(request.user, details, picked, visible)
    except ReportError as error:
        return 400, ErrorResponse(detail=str(error))
    return StructureReportResponse(status="recorded")


@router.get(
    "/structures/{structure_id}",
    auth=AuthBearer(),
    response={200: UniverseStructure, 403: ErrorResponse, 404: ErrorResponse},
)
def get_structure(request, structure_id: int):
    if not can_use_feature(request.user, STRUCTURES_FEATURE):
        return 403, ErrorResponse(detail="You cannot view structures")
    structure = _visible(request.user).filter(id=structure_id).first()
    if structure is None:
        return 404, ErrorResponse(detail="Structure not found")
    return _serialize([structure], request.user)[0]


@router.patch(
    "/structures/{structure_id}/visibility",
    auth=AuthBearer(),
    response={200: UniverseStructure, 403: ErrorResponse, 404: ErrorResponse},
)
def set_visibility(request, structure_id: int, payload: VisibilityRequest):
    structure = _visible(request.user).filter(id=structure_id).first()
    if structure is None:
        return 404, ErrorResponse(detail="Structure not found")
    if not can_change_visibility(request.user, structure):
        return 403, ErrorResponse(
            detail="Only the owning corporation's directors and station "
            "managers can change who sees this structure"
        )
    structure.visibility = payload.visibility
    structure.save(update_fields=["visibility"])
    return _serialize([structure], request.user)[0]


@router.post(
    "/structures/{structure_id}/confirm",
    auth=AuthBearer(),
    response={200: UniverseStructure, 403: ErrorResponse, 404: ErrorResponse},
)
def confirm_structure(request, structure_id: int):
    """A pilot saw it still standing."""
    if not can_use_feature(request.user, STRUCTURES_FEATURE):
        return 403, ErrorResponse(detail="You cannot report structures")
    structure = _visible(request.user).filter(id=structure_id).first()
    if structure is None or not can_see_structure(request.user, structure):
        return 404, ErrorResponse(detail="Structure not found")
    structure.last_confirmed_at = timezone.now()
    structure.last_confirmed_by = request.user
    structure.save(update_fields=["last_confirmed_at", "last_confirmed_by"])
    return _serialize([structure], request.user)[0]


# How long a finished timer stays on the board.
TIMERS_DONE_WINDOW = timedelta(days=7)


@router.get(
    "/timers",
    auth=AuthBearer(),
    response={200: UniverseTimerList, 403: ErrorResponse},
)
def list_timers(request):
    """Every structure timer, across all campaigns: upcoming soonest first,
    then the last week's finished timers, newest first."""
    if not can_use_feature(request.user, TIMERS_FEATURE):
        return 403, ErrorResponse(detail="You cannot view structure timers")
    now = timezone.now()
    timers = (
        EveStructureTimer.objects.filter(timer__gte=now - TIMERS_DONE_WINDOW)
        .select_related("structure", "campaign")
        .prefetch_related(
            Prefetch(
                "campaign_structures",
                to_attr="recon_rows",
            ),
            "campaign_structures__campaign",
        )
    )
    hidden = set(
        EveStructure.objects.filter(
            id__in=[t.structure_id for t in timers if t.structure_id]
        )
        .exclude(id__in=visible_structures(request.user).values("id"))
        .values_list("id", flat=True)
    )
    rows = []
    for timer in timers:
        if timer.structure_id in hidden:
            continue
        stage, final = timer_stage(timer.type, timer.state)
        campaign = timer.campaign
        recon = timer.recon_rows[0] if timer.recon_rows else None
        if campaign is None and recon is not None:
            campaign = recon.campaign
        rows.append(
            UniverseTimer(
                id=timer.id,
                name=timer.structure.name if timer.structure else timer.name,
                structure_type=timer.type,
                type_name=TYPE_NAMES.get(timer.type, timer.type),
                type_id=(
                    timer.structure.type_id
                    if timer.structure
                    else (recon.type_id if recon else None)
                ),
                system=timer.system_name,
                state=timer.state,
                stage=stage,
                final=final,
                at=timer.timer,
                alliance_name=timer.alliance_name or "",
                corporation_name=timer.corporation_name or "",
                campaign_name=campaign.name if campaign else "",
                campaign_slug=campaign.slug if campaign else "",
                done=timer.timer <= now,
            )
        )
    upcoming = sorted((r for r in rows if not r.done), key=lambda r: r.at)
    done = sorted(
        (r for r in rows if r.done), key=lambda r: r.at, reverse=True
    )
    return UniverseTimerList(
        timers=upcoming + done,
        can_add=can_use_feature(request.user, "structures.timers.manage"),
    )


@router.get(
    "/moons",
    auth=AuthBearer(),
    response={200: UniverseMoonList, 403: ErrorResponse},
)
def list_moons(request):
    """Every moon we know about. Contents (ores, scans, ISK a month) are
    null unless the caller may see them, so the shape never changes."""
    if not can_use_feature(request.user, MOONS_FEATURE):
        return 403, ErrorResponse(detail="You cannot view moons")
    contents = can_see_moon_contents(request.user)
    moons = list(
        EveMoon.objects.prefetch_related(
            Prefetch(
                "evemoondistribution_set",
                queryset=EveMoonDistribution.objects.order_by(
                    "-yield_percent"
                ),
                to_attr="ores",
            ),
            Prefetch(
                "scans",
                queryset=EveMoonScan.objects.order_by("-reported_at", "-id"),
                to_attr="scan_rows",
            ),
        )
    )
    user_ids = {m.reported_by_id for m in moons if m.reported_by_id}
    for moon in moons:
        user_ids |= {
            s.reported_by_id for s in moon.scan_rows if s.reported_by_id
        }
    refs = primary_refs_for_users(user_ids)
    rows = []
    for moon in moons:
        latest = moon.scan_rows[0] if moon.scan_rows else None
        row = UniverseMoon(
            id=moon.id,
            system=moon.system,
            planet=moon.planet,
            moon=moon.moon,
            reported_by=_pilot(refs, moon.reported_by_id),
            last_scanned_at=latest.reported_at if latest else None,
        )
        if contents:
            row.rarity = (
                max(
                    (ORE_RARITY.get(o.ore, 0) for o in moon.ores), default=None
                )
                or None
            )
            row.monthly_revenue = moon.monthly_revenue
            row.ores = [
                MoonOre(ore=o.ore, yield_percent=float(o.yield_percent))
                for o in moon.ores
            ]
            row.scans = [
                MoonScanRef(
                    reported_at=s.reported_at,
                    reported_by=_pilot(refs, s.reported_by_id),
                    revenue=s.revenue,
                )
                for s in moon.scan_rows
            ]
        rows.append(row)
    if contents:
        rows.sort(key=lambda r: -(r.monthly_revenue or 0))
    else:
        rows.sort(
            key=lambda r: r.last_scanned_at
            or datetime.min.replace(tzinfo=dt_timezone.utc),
            reverse=True,
        )
    return UniverseMoonList(
        moons=rows, can_view_contents=contents, can_report=True
    )


@router.post(
    "/moons/report",
    auth=AuthBearer(),
    response={200: MoonParsingResult, 403: ErrorResponse},
)
def report_moons(request, payload: MoonReportRequest):
    """Paste from the moon survey scanner. Any pilot who sees moons can
    report them; each moon's scan is kept."""
    if not can_use_feature(request.user, MOONS_FEATURE):
        return 403, ErrorResponse(detail="You cannot report moons")
    return process_moon_paste(payload.paste, user_id=request.user.id)


__all__ = ["router", "REPORTABLE_TYPES"]
