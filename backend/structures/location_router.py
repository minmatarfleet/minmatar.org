"""Structure browser API: /api/structures/locations/..."""

from datetime import datetime
from typing import List, Optional

from django.utils import timezone
from ninja import Router, Schema

from app.errors import ErrorResponse
from authentication import AuthBearer, AuthOptional
from eveonline.models import EveLocation
from industry.helpers.facility_api import facility_key_for_system

from . import locations as svc
from .models import LocationAudienceGroup, LocationChange, LocationSubmission

router = Router(tags=["Structure browser"])


class LocationModule(Schema):
    name: str
    slot: str
    size: str
    label: str


class LocationHolding(Schema):
    clones: int
    items: int


class LocationCard(Schema):
    location_id: int
    name: str
    short_name: str
    solar_system_id: int
    solar_system_name: str
    security: Optional[float]
    is_structure: bool
    type_id: Optional[int]
    type_name: str
    staging: bool
    fleets: bool
    freight: bool
    market: bool
    prices: bool
    industry_orders: int
    audience: str
    audience_groups: List[str]
    good_for: List[str]
    rigs: List[LocationModule]
    services: List[str]
    fitting_scanned_at: Optional[datetime]
    reinforce_hour: Optional[int]
    route_count: int
    planner_facility: Optional[str]
    freighter_dock: bool
    you: LocationHolding


class LocationList(Schema):
    locations: List[LocationCard]
    can_manage: bool
    can_add: bool


class LocationChangeEntry(Schema):
    id: int
    kind: str
    summary: str
    details: dict
    created_at: datetime
    user_name: str
    character_id: Optional[int]


class LocationDetail(LocationCard):
    description: str
    fitting: List[LocationModule]
    audience_tribe_group_ids: List[int]
    changes: List[LocationChangeEntry]
    can_manage: bool


class LocationPatch(Schema):
    short_name: Optional[str] = None
    description: Optional[str] = None
    reinforce_hour: Optional[int] = None
    clear_reinforce_hour: bool = False
    audience: Optional[str] = None
    audience_tribe_group_ids: Optional[List[int]] = None
    good_for: Optional[List[str]] = None
    freight_active: Optional[bool] = None
    fleets_active: Optional[bool] = None
    market_active: Optional[bool] = None
    prices_active: Optional[bool] = None


class LocationFittingPaste(Schema):
    text: str


class LocationPaste(Schema):
    text: str


class LocationMatch(Schema):
    status: str
    location_id: Optional[int]
    source: str
    name: str
    solar_system_name: str
    type_id: Optional[int]
    type_name: str
    found_with: str


class LocationParseResult(Schema):
    name: str
    solar_system_name: str
    type_id: Optional[int]
    reinforce_hour: Optional[int]
    parts: List[str]
    modules: List[LocationModule]
    match: LocationMatch


class LocationDocked(Schema):
    character_id: int
    character_name: str
    location_id: int
    name: str
    listed: bool


class LocationSubmissionRequest(Schema):
    paste_text: str = ""
    name: str
    location_id: Optional[int] = None
    id_source: str = ""
    type_id: Optional[int] = None
    short_name: str = ""
    reinforce_hour: Optional[int] = None
    audience: str = EveLocation.AUDIENCE_ALLIANCE
    audience_tribe_group_ids: List[int] = []
    good_for: List[str] = []
    description: str = ""


class LocationSubmissionRow(Schema):
    id: int
    name: str
    location_id: Optional[int]
    solar_system_name: str
    type_id: Optional[int]
    type_name: str
    audience: str
    good_for: List[str]
    rig_count: int
    status: str
    submitted_by: str
    created_at: datetime


class LocationDecline(Schema):
    reason: str = ""


class LocationAttention(Schema):
    kind: str
    title: str
    detail: str
    location_id: Optional[int]


class LocationManageRow(Schema):
    location_id: int
    name: str
    short_name: str
    solar_system_name: str
    type_id: Optional[int]
    type_name: str
    is_structure: bool
    freight: bool
    fleets: bool
    market: bool
    prices: bool
    staging: bool
    price_baseline: bool
    audience: str
    audience_groups: List[str]


class LocationManage(Schema):
    submissions: List[LocationSubmissionRow]
    attention: List[LocationAttention]
    locations: List[LocationManageRow]


def _type_name(type_id: Optional[int], is_structure: bool) -> str:
    if type_id in svc.STRUCTURE_TYPE_NAMES:
        return svc.STRUCTURE_TYPE_NAMES[type_id]
    return "Structure" if is_structure else "NPC station"


def _group_names(location) -> List[str]:
    names = []
    for row in location.audience_groups.all():
        if row.tribe_group_id:
            names.append(row.tribe_group.name)
        elif row.corporation_id:
            names.append(row.corporation.name)
    return names


def _security_map(system_ids) -> dict:
    # pylint: disable=import-outside-toplevel
    from eveuniverse.models import EveSolarSystem

    return dict(
        EveSolarSystem.objects.filter(id__in=set(system_ids)).values_list(
            "id", "security_status"
        )
    )


MEDIUM_STRUCTURES = {35832, 35825, 35835}  # Astrahus, Raitaru, Athanor


def _station_types(rows) -> dict:
    """NPC station type ids from eveuniverse, for card art."""
    # pylint: disable=import-outside-toplevel
    from eveuniverse.models import EveStation

    ids = [
        row.location_id
        for row in rows
        if not row.type_id and row.location_id < 100_000_000
    ]
    if not ids:
        return {}
    return dict(
        EveStation.objects.filter(id__in=ids).values_list("id", "eve_type_id")
    )


def _card(
    location, you, orders, security=None, routes=None, stations=None
) -> dict:
    fitting = location.fitting or []
    type_id = location.type_id or (stations or {}).get(location.location_id)
    sec = (security or {}).get(location.solar_system_id)
    return {
        "location_id": location.location_id,
        "name": location.location_name,
        "short_name": location.short_name,
        "solar_system_id": location.solar_system_id,
        "solar_system_name": location.solar_system_name,
        "security": round(sec, 4) if sec is not None else None,
        "is_structure": location.is_structure,
        "type_id": type_id,
        "type_name": _type_name(location.type_id, location.is_structure),
        "staging": location.staging_active,
        "fleets": location.fleets_active,
        "freight": location.freight_active,
        "market": location.market_active,
        "prices": location.prices_active,
        "industry_orders": orders.get(location.location_id, 0),
        "audience": location.audience,
        "audience_groups": _group_names(location),
        "good_for": location.good_for or [],
        "rigs": [m for m in fitting if m.get("slot") == "rig"],
        "services": [
            m.get("label", "") for m in fitting if m.get("slot") == "service"
        ],
        "fitting_scanned_at": location.fitting_scanned_at,
        "reinforce_hour": location.reinforce_hour,
        "route_count": (routes or {}).get(location.location_id, 0),
        "planner_facility": facility_key_for_system(location.solar_system_id),
        "freighter_dock": location.type_id not in MEDIUM_STRUCTURES,
        "you": you.get(location.location_id, {"clones": 0, "items": 0}),
    }


def _user(request):
    user = getattr(request, "user", None)
    return user if user is not None and user.is_authenticated else None


@router.get(
    "",
    auth=AuthOptional(),
    response={200: LocationList},
    description="Locations on the structure browser that this user may see.",
)
def list_locations(request):
    user = _user(request)
    rows = list(
        svc.visible_locations(user)
        .prefetch_related(
            "audience_groups__tribe_group", "audience_groups__corporation"
        )
        .order_by("-staging_active", "location_name")
    )
    ids = [row.location_id for row in rows]
    you = svc.holdings(user, ids)
    orders = svc.open_order_counts(ids)
    security = _security_map(row.solar_system_id for row in rows)
    routes = svc.route_counts(ids)
    stations = _station_types(rows)
    return {
        "locations": [
            _card(row, you, orders, security, routes, stations) for row in rows
        ],
        "can_manage": bool(user) and svc.can_manage(user),
        "can_add": bool(user) and svc.can_view_alliance(user),
    }


def _changes(location) -> List[dict]:
    out = []
    for change in LocationChange.objects.filter(
        location=location
    ).select_related("user")[:100]:
        character_id = None
        user_name = "The site"
        if change.user_id:
            user_name = change.user.username
            # pylint: disable=import-outside-toplevel
            from eveonline.helpers.characters import user_primary_character

            primary = user_primary_character(change.user)
            if primary:
                user_name = primary.character_name
                character_id = primary.character_id
        out.append(
            {
                "id": change.id,
                "kind": change.kind,
                "summary": change.summary,
                "details": change.details,
                "created_at": change.created_at,
                "user_name": user_name,
                "character_id": character_id,
            }
        )
    return out


@router.post(
    "/parse",
    auth=AuthBearer(),
    response={200: LocationParseResult, 403: ErrorResponse},
    description="Read a paste from the EVE client and look for the structure's ID.",
)
def post_parse(request, payload: LocationPaste):
    if not svc.can_view_alliance(request.user):
        return 403, {"detail": "You can't add structures."}
    parsed = svc.parse_paste(payload.text)
    match = svc.find_structure(request.user, parsed.name, parsed.type_id)
    return {
        "name": parsed.name,
        "solar_system_name": parsed.solar_system_name,
        "type_id": parsed.type_id or match.type_id,
        "reinforce_hour": parsed.reinforce_hour,
        "parts": parsed.parts,
        "modules": svc.modules_as_json(parsed.modules),
        "match": {
            "status": match.status,
            "location_id": match.location_id,
            "source": match.source,
            "name": match.name or parsed.name,
            "solar_system_name": match.solar_system_name
            or parsed.solar_system_name,
            "type_id": match.type_id or parsed.type_id,
            "type_name": _type_name(match.type_id or parsed.type_id, True),
            "found_with": match.found_with,
        },
    }


@router.get(
    "/docked/characters",
    auth=AuthBearer(),
    response={200: List[LocationDocked], 403: ErrorResponse},
    description="Where the user's characters are docked right now.",
)
def get_docked(request):
    if not svc.can_view_alliance(request.user):
        return 403, {"detail": "You can't add structures."}
    return svc.docked_locations(request.user)


def _submission_row(row: LocationSubmission) -> dict:
    submitted_by = ""
    if row.submitted_by_id:
        # pylint: disable=import-outside-toplevel
        from eveonline.helpers.characters import user_primary_character

        primary = user_primary_character(row.submitted_by)
        submitted_by = (
            primary.character_name if primary else row.submitted_by.username
        )
    return {
        "id": row.id,
        "name": row.name,
        "location_id": row.location_id,
        "solar_system_name": row.solar_system_name,
        "type_id": row.type_id,
        "type_name": _type_name(row.type_id, True),
        "audience": row.audience,
        "good_for": row.good_for,
        "rig_count": svc.fitting_summary(row.fitting)["rig"],
        "status": row.status,
        "submitted_by": submitted_by,
        "created_at": row.created_at,
    }


@router.post(
    "/submissions",
    auth=AuthBearer(),
    response={
        201: LocationSubmissionRow,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    description="Send a structure for approval.",
)
def post_submission(request, payload: LocationSubmissionRequest):
    if not svc.can_view_alliance(request.user):
        return 403, {"detail": "You can't add structures."}
    name = payload.name.strip()
    if not name:
        return 400, {"detail": "The structure needs a name."}
    if payload.audience not in dict(EveLocation.AUDIENCE_CHOICES):
        return 400, {"detail": "Unknown audience."}
    if any(v not in svc.GOOD_FOR_CHOICES for v in payload.good_for):
        return 400, {"detail": "Unknown Good for tag."}
    if (
        payload.reinforce_hour is not None
        and not 0 <= payload.reinforce_hour <= 23
    ):
        return 400, {"detail": "Reinforce hour is 0 to 23."}
    if (
        payload.location_id
        and EveLocation.objects.filter(
            location_id=payload.location_id
        ).exists()
    ):
        return 400, {"detail": "This structure is already on the list."}
    if LocationSubmission.objects.filter(
        name__iexact=name, status=LocationSubmission.STATUS_PENDING
    ).exists():
        return 400, {
            "detail": "Someone already sent this structure for approval."
        }
    parsed = svc.parse_paste(payload.paste_text)
    system, _ = svc.split_structure_name(name)
    row = LocationSubmission.objects.create(
        location_id=payload.location_id,
        id_source=payload.id_source[:16],
        name=name,
        short_name=(payload.short_name or name)[:32],
        type_id=payload.type_id or parsed.type_id,
        solar_system_name=system,
        paste_text=payload.paste_text,
        fitting=svc.modules_as_json(parsed.modules),
        reinforce_hour=(
            payload.reinforce_hour
            if payload.reinforce_hour is not None
            else parsed.reinforce_hour
        ),
        audience=payload.audience,
        audience_tribe_group_ids=payload.audience_tribe_group_ids,
        good_for=payload.good_for,
        description=payload.description,
        submitted_by=request.user,
    )
    return 201, _submission_row(row)


@router.get(
    "/manage/overview",
    auth=AuthBearer(),
    response={200: LocationManage, 403: ErrorResponse},
    description="Approval queue, things to fix and every location.",
)
def get_manage(request):
    if not svc.can_manage(request.user):
        return _forbidden()
    locations = list(
        EveLocation.objects.all()
        .prefetch_related(
            "audience_groups__tribe_group", "audience_groups__corporation"
        )
        .order_by("-staging_active", "-freight_active", "short_name")
    )
    pending = (
        LocationSubmission.objects.filter(
            status=LocationSubmission.STATUS_PENDING
        )
        .select_related("submitted_by")
        .order_by("created_at")
    )
    return {
        "submissions": [_submission_row(row) for row in pending],
        "attention": svc.attention_items(locations),
        "locations": [
            {
                "location_id": row.location_id,
                "name": row.location_name,
                "short_name": row.short_name,
                "solar_system_name": row.solar_system_name,
                "type_id": row.type_id,
                "type_name": _type_name(row.type_id, row.is_structure),
                "is_structure": row.is_structure,
                "freight": row.freight_active,
                "fleets": row.fleets_active,
                "market": row.market_active,
                "prices": row.prices_active,
                "staging": row.staging_active,
                "price_baseline": row.price_baseline,
                "audience": row.audience,
                "audience_groups": _group_names(row),
            }
            for row in locations
        ],
    }


@router.post(
    "/submissions/{submission_id}/approve",
    auth=AuthBearer(),
    response={
        200: LocationDetail,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def approve(request, submission_id: int):
    if not svc.can_manage(request.user):
        return _forbidden()
    row = LocationSubmission.objects.filter(id=submission_id).first()
    if row is None:
        return 404, {"detail": "Submission not found."}
    try:
        location = svc.approve_submission(row, request.user)
    except svc.ApprovalError as error:
        return 400, {"detail": str(error)}
    return get_location(request, location.location_id)


@router.post(
    "/submissions/{submission_id}/decline",
    auth=AuthBearer(),
    response={
        200: LocationSubmissionRow,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def decline(request, submission_id: int, payload: LocationDecline):
    if not svc.can_manage(request.user):
        return _forbidden()
    row = LocationSubmission.objects.filter(id=submission_id).first()
    if row is None:
        return 404, {"detail": "Submission not found."}
    try:
        svc.decline_submission(row, request.user, payload.reason)
    except svc.ApprovalError as error:
        return 400, {"detail": str(error)}
    return _submission_row(row)


# Routes with a path parameter come last so /parse, /submissions and
# /manage/... are matched first.
@router.get(
    "/{location_id}",
    auth=AuthOptional(),
    response={200: LocationDetail, 404: ErrorResponse},
)
def get_location(request, location_id: int):
    user = _user(request)
    location = (
        svc.visible_locations(user).filter(location_id=location_id).first()
    )
    if location is None:
        return 404, {"detail": "Location not found."}
    ids = [location.location_id]
    card = _card(
        location,
        svc.holdings(user, ids),
        svc.open_order_counts(ids),
        _security_map([location.solar_system_id]),
        svc.route_counts(ids),
        _station_types([location]),
    )
    card.update(
        {
            "description": location.description,
            "fitting": location.fitting or [],
            "audience_tribe_group_ids": [
                row.tribe_group_id
                for row in location.audience_groups.all()
                if row.tribe_group_id
            ],
            "changes": _changes(location),
            "can_manage": bool(user) and svc.can_manage(user),
        }
    )
    return card


def _forbidden():
    return 403, {"detail": "You can't manage locations."}


def _patch_error(location, sent: dict) -> Optional[str]:
    if "audience" in sent and sent["audience"] not in dict(
        EveLocation.AUDIENCE_CHOICES
    ):
        return "Unknown audience."
    if "good_for" in sent and any(
        v not in svc.GOOD_FOR_CHOICES for v in sent["good_for"]
    ):
        return "Unknown Good for tag."
    hour = sent.get("reinforce_hour")
    if hour is not None and not 0 <= hour <= 23:
        return "Reinforce hour is 0 to 23."
    if sent.get("prices_active") and not sent.get(
        "market_active", location.market_active
    ):
        return "Price tracking needs Market."
    return None


def _patch_details(location, user, sent: dict):
    short = (sent.get("short_name") or "")[:32]
    if short and short != location.short_name:
        location.short_name = short
        svc.record_change(
            location, user, "details", "renamed it", {"short_name": short}
        )
    description = sent.get("description")
    if "description" in sent and (description or "") != location.description:
        location.description = description or ""
        svc.record_change(location, user, "details", "edited About")
    hour = sent.get("reinforce_hour")
    if (
        sent.get("clear_reinforce_hour")
        and location.reinforce_hour is not None
    ):
        location.reinforce_hour = None
        svc.record_change(
            location, user, "details", "cleared the reinforce time"
        )
    elif not sent.get("clear_reinforce_hour") and hour is not None:
        if hour != location.reinforce_hour:
            location.reinforce_hour = hour
            svc.record_change(
                location,
                user,
                "details",
                "set the reinforce time",
                {"hour": hour},
            )
    good_for = sent.get("good_for")
    if good_for is not None and sorted(good_for) != sorted(
        location.good_for or []
    ):
        location.good_for = good_for
        svc.record_change(
            location,
            user,
            "details",
            "changed Good for",
            {"good_for": good_for},
        )


def _patch_audience(location, user, sent: dict):
    if "audience" not in sent:
        return
    before = location.get_audience_display()
    old_groups = sorted(
        location.audience_groups.exclude(tribe_group__isnull=True).values_list(
            "tribe_group_id", flat=True
        )
    )
    new_groups = []
    if sent["audience"] == EveLocation.AUDIENCE_GROUPS:
        new_groups = sorted(sent.get("audience_tribe_group_ids") or [])
    if sent["audience"] == location.audience and new_groups == old_groups:
        return
    location.audience = sent["audience"]
    location.audience_groups.all().delete()
    for group_id in new_groups:
        LocationAudienceGroup.objects.create(
            location=location, tribe_group_id=group_id
        )
    svc.record_change(
        location,
        user,
        "audience",
        "changed who can see it",
        {"from": before, "to": location.get_audience_display()},
    )


SITE_FLAGS = (
    ("freight_active", "Freight"),
    ("fleets_active", "Fleet form-up"),
    ("market_active", "Market"),
    ("prices_active", "Price tracking"),
)


def _patch_flags(location, user, sent: dict):
    if sent.get("freight_active") is False and location.freight_active:
        # Same meaning as the admin: turning Freight off retires its routes.
        # pylint: disable=import-outside-toplevel
        from django.db.models import Q
        from freight.models import EveFreightRoute

        EveFreightRoute.objects.filter(
            Q(origin_location=location) | Q(destination_location=location)
        ).update(active=False)
    for flag, label in SITE_FLAGS:
        value = sent.get(flag)
        if value is None or getattr(location, flag) == value:
            continue
        setattr(location, flag, value)
        svc.record_change(
            location,
            user,
            "flags",
            f"turned {'on' if value else 'off'} {label}",
        )


@router.patch(
    "/{location_id}",
    auth=AuthBearer(),
    response={
        200: LocationDetail,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def patch_location(request, location_id: int, payload: LocationPatch):
    if not svc.can_manage(request.user):
        return _forbidden()
    location = EveLocation.objects.filter(location_id=location_id).first()
    if location is None:
        return 404, {"detail": "Location not found."}
    sent = payload.dict(exclude_unset=True)
    error = _patch_error(location, sent)
    if error:
        return 400, {"detail": error}
    _patch_flags(location, request.user, sent)
    _patch_details(location, request.user, sent)
    _patch_audience(location, request.user, sent)
    location.save()
    return get_location(request, location_id)


@router.post(
    "/{location_id}/fitting",
    auth=AuthBearer(),
    response={
        200: LocationDetail,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    description="Paste a new ship scan for a location.",
)
def post_fitting(request, location_id: int, payload: LocationFittingPaste):
    if not svc.can_view_alliance(request.user):
        return 403, {"detail": "You can't update structures."}
    location = (
        svc.visible_locations(request.user)
        .filter(location_id=location_id)
        .first()
    )
    if location is None:
        return 404, {"detail": "Location not found."}
    parsed = svc.parse_paste(payload.text)
    if not parsed.modules:
        return 400, {"detail": "No Standup modules found in the paste."}
    new = svc.modules_as_json(parsed.modules)
    diff = svc.fitting_diff(location.fitting or [], new)
    location.fitting = new
    location.fitting_text = payload.text

    location.fitting_scanned_at = timezone.now()
    location.save()
    svc.record_change(
        location, request.user, "fitting", "pasted a new ship scan", diff
    )
    return get_location(request, location_id)
