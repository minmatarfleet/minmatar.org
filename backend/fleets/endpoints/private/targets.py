"""Ship targets: how many of each kind of ship the FC wants, on any fleet."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.endpoints.helpers import _fleet_authorized, _fleet_manager
from fleets.endpoints.private.invites import can_manage_invites
from fleets.endpoints.private.schemas import (
    MyTargetHangarResponse,
    ShipTargetProgress,
    ShipTargetsRequest,
    TargetLineOwner,
    TargetSuggestionsResponse,
    UnmatchedHull,
)
from fleets.helpers.private_fleets import (
    PrivateFleetError,
    replace_targets,
    target_progress,
)
from fleets.helpers.ship_targets import (
    doctrine_target_lines,
    line_owners,
    my_target_hangar,
    past_target_fleets,
    unmatched_hulls,
)
from fleets.models import EveFleet, EveFleetShipTarget


def get_fleet_targets(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet is None or not _fleet_authorized(request, fleet):
        return 404, None
    return [ShipTargetProgress(**row) for row in target_progress(fleet)]


def put_fleet_targets(request, fleet_id: int, payload: ShipTargetsRequest):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet is None or not _fleet_authorized(request, fleet):
        return 404, None
    if not _fleet_manager(request, fleet):
        return 403, None
    try:
        replace_targets(fleet, [line.model_dump() for line in payload.lines])
    except PrivateFleetError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))
    if fleet.invite_only:
        # pylint: disable=import-outside-toplevel
        from fleets.tasks import refresh_private_fleet_summary

        refresh_private_fleet_summary.delay(fleet.id)
    return 200, [ShipTargetProgress(**row) for row in target_progress(fleet)]


def get_target_suggestions(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet is None or not _fleet_authorized(request, fleet):
        return 404, None
    if not _fleet_manager(request, fleet):
        return 403, None
    return 200, TargetSuggestionsResponse(
        doctrine=doctrine_target_lines(fleet),
        past_fleets=past_target_fleets(request.user, fleet.id),
    )


def get_unmatched_hulls(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet is None or not _fleet_authorized(request, fleet):
        return 404, None
    if not _fleet_manager(request, fleet):
        return 403, None
    return 200, [UnmatchedHull(**row) for row in unmatched_hulls(fleet)]


def get_line_owners(request, fleet_id: int, target_id: int):
    fleet = EveFleet.objects.filter(
        id=fleet_id, invite_only=True, declassified_at__isnull=True
    ).first()
    # Same rule as the Invites tab: don't confirm a private fleet exists.
    if fleet is None or not can_manage_invites(request.user, fleet):
        return 404, None
    target = EveFleetShipTarget.objects.filter(
        id=target_id, eve_fleet=fleet
    ).first()
    if target is None:
        return 404, None
    return 200, [TargetLineOwner(**row) for row in line_owners(fleet, target)]


def get_my_target_hangar(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet is None or not _fleet_authorized(request, fleet):
        return 404, None
    return 200, MyTargetHangarResponse(**my_target_hangar(fleet, request.user))


ROUTES = (
    (
        "get",
        "/{fleet_id}/targets",
        {
            "auth": AuthBearer(),
            "response": {200: List[ShipTargetProgress], 404: None},
            "description": (
                "The fleet's ship targets with how many characters signed "
                "up for each line."
            ),
        },
        get_fleet_targets,
    ),
    (
        "put",
        "/{fleet_id}/targets",
        {
            "auth": AuthBearer(),
            "response": {
                200: List[ShipTargetProgress],
                400: ErrorResponse,
                403: None,
                404: None,
            },
            "description": (
                "Replace the fleet's ship targets. A hull or EVE group can "
                "be on one line only."
            ),
        },
        put_fleet_targets,
    ),
    (
        "get",
        "/{fleet_id}/targets/suggestions",
        {
            "auth": AuthBearer(),
            "response": {
                200: TargetSuggestionsResponse,
                403: None,
                404: None,
            },
            "description": (
                "Lines to start the fleet's targets from: one per EVE "
                "group in its doctrine, and your recent fleets' targets."
            ),
        },
        get_target_suggestions,
    ),
    (
        "get",
        "/{fleet_id}/targets/unmatched",
        {
            "auth": AuthBearer(),
            "response": {200: List[UnmatchedHull], 403: None, 404: None},
            "description": "Hulls signed up that no target line counts.",
        },
        get_unmatched_hulls,
    ),
    (
        "get",
        "/{fleet_id}/targets/{target_id}/owners",
        {
            "auth": AuthBearer(),
            "response": {200: List[TargetLineOwner], 404: None},
            "description": (
                "Private fleets: alliance players not yet invited who own "
                "a hull this line counts, from ESI assets. The fleet's "
                "creator and Strategic FCs only."
            ),
        },
        get_line_owners,
    ),
    (
        "get",
        "/{fleet_id}/targets/mine",
        {
            "auth": AuthBearer(),
            "response": {200: MyTargetHangarResponse, 404: None},
            "description": (
                "For the ship picker: the target line each doctrine hull "
                "counts toward, and the doctrine hulls each of your "
                "characters owns."
            ),
        },
        get_my_target_hangar,
    ),
)
