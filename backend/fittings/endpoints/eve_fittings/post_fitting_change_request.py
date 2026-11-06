"""POST {fitting_id}/change-requests - preview or submit a fitting edit."""

from django.core.exceptions import ValidationError

from app.errors import ErrorResponse
from authentication import AuthBearer
from fittings.eft import parse_eft_header
from fittings.endpoints.change_requests.schemas import (
    ChangePreviewResponse,
    FittingChangeRequest,
)
from fittings.helpers.change_request_api import (
    can_edit_doctrines,
    eft_ship_matches,
    fitting_diffs,
    serialize_request,
)
from fittings.helpers.fitting_changes import (
    build_fitting_payload_from_instance,
    fitting_payload_changed,
    submit_fitting_change_request,
)
from fittings.models import EveFitting

PATH = "{int:fitting_id}/change-requests"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: ChangePreviewResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
}


def post_fitting_change_request(
    request, fitting_id: int, payload: FittingChangeRequest
):
    if not can_edit_doctrines(request.user):
        return 403, {"detail": "You cannot propose fitting changes"}
    fitting = EveFitting.objects.filter(id=fitting_id).first()
    if not fitting:
        return 404, {"detail": "Fitting not found"}

    eft = payload.eft_format.strip()
    if not parse_eft_header(eft)[1]:
        return 400, {
            "detail": "EFT header must include a fitting name: [Ship, Name]."
        }
    if not eft_ship_matches(fitting, eft):
        return 400, {"detail": "The EFT must be for the same ship hull."}
    try:
        tags = EveFitting.coerce_tags(payload.tags)
    except ValidationError as exc:
        return 400, {"detail": "; ".join(exc.messages)}
    derived = EveFitting.fitting_name_from_eft(eft)
    if EveFitting.objects.filter(name=derived).exclude(pk=fitting.pk).exists():
        return 400, {"detail": f"A fitting named {derived!r} already exists."}

    proposed = build_fitting_payload_from_instance(fitting)
    proposed.update(
        {"eft_format": eft, "description": payload.description, "tags": tags}
    )
    if not fitting_payload_changed(fitting, proposed):
        return 400, {"detail": "Nothing changed."}
    diffs = fitting_diffs(fitting, proposed)
    if payload.preview:
        return {"diffs": diffs}
    try:
        change_request = submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload=proposed,
            user=request.user,
        )
    except PermissionError as exc:
        return 403, {"detail": str(exc)}
    except ValueError as exc:
        return 409, {"detail": str(exc)}
    return {
        "diffs": diffs,
        "request": serialize_request(request.user, "fitting", change_request),
    }
