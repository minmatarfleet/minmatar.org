"""Ship targets: how many of each kind of ship the FC wants, on any fleet."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.endpoints.helpers import _fleet_authorized, _fleet_manager
from fleets.endpoints.private.schemas import (
    ShipTargetProgress,
    ShipTargetsRequest,
)
from fleets.helpers.private_fleets import (
    PrivateFleetError,
    replace_targets,
    target_progress,
)
from fleets.models import EveFleet


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
)
