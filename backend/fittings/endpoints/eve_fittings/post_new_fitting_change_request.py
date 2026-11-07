"""POST new/change-requests - read pasted EFT, or submit it as a new fitting.

The doctrine editor uses this when a fit is not in the catalog yet. The new
fitting waits for review like an admin-created one, and a doctrine change
that lists it approves it too.
"""

from django.core.exceptions import ValidationError
from eveuniverse.models import EveType

from app.errors import ErrorResponse
from authentication import AuthBearer
from fittings.eft import parse_eft_header
from fittings.endpoints.change_requests.schemas import (
    NewFittingRequest,
    NewFittingResponse,
)
from fittings.helpers.change_request_api import (
    can_edit_doctrines,
    serialize_request,
)
from fittings.helpers.fitting_changes import (
    fitting_name_taken,
    submit_new_fitting,
)
from fittings.models import EveFitting

PATH = "new/change-requests"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: NewFittingResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        409: ErrorResponse,
    },
}


def _item_lines(eft: str) -> int:
    lines = [line.strip() for line in eft.splitlines()[1:]]
    return sum(1 for line in lines if line and not line.startswith("["))


def post_new_fitting_change_request(request, payload: NewFittingRequest):
    if not can_edit_doctrines(request.user):
        return 403, {"detail": "You cannot propose fitting changes"}

    eft = payload.eft_format.strip()
    ship_name, name = parse_eft_header(eft)
    if not name:
        return 400, {
            "detail": "EFT header must include a fitting name: [Ship, Name]."
        }
    ship = (
        EveType.objects.filter(name=ship_name)
        .select_related("eve_group")
        .first()
    )
    if ship is None:
        return 400, {"detail": f"Unknown ship {ship_name!r}."}
    if fitting_name_taken(name):
        return 400, {"detail": f"A fitting named {name!r} already exists."}
    try:
        tags = EveFitting.coerce_tags(payload.tags)
    except ValidationError as exc:
        return 400, {"detail": "; ".join(exc.messages)}

    response = {
        "name": name,
        "ship_id": ship.id,
        "ship_name": ship.name,
        "ship_group": ship.eve_group.name if ship.eve_group else "",
        "item_lines": _item_lines(eft),
    }
    if payload.preview:
        return response
    try:
        fitting, change_request = submit_new_fitting(
            name=name,
            ship_id=ship.id,
            eft=eft,
            description=payload.description,
            tags=tags,
            user=request.user,
        )
    except PermissionError as exc:
        return 403, {"detail": str(exc)}
    except ValueError as exc:
        return 409, {"detail": str(exc)}
    return {
        **response,
        "fitting_id": fitting.pk,
        "request": serialize_request(request.user, "fitting", change_request),
    }
