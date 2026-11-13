"""POST {doctrine_id}/change-requests - preview or submit a doctrine edit."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from fittings.endpoints.change_requests.schemas import (
    ChangePreviewResponse,
    DoctrineChangeRequestBody,
)
from fittings.helpers.change_request_api import (
    can_edit_doctrines,
    doctrine_diffs,
    serialize_request,
)
from fittings.helpers.doctrine_changes import (
    change_tier_for,
    doctrine_state_changed,
    pending_doctrine_request_exists,
    submit_doctrine_change_request,
)
from fittings.models import (
    DOCTRINE_FITTING_ROLES,
    EveDoctrine,
    EveFitting,
    location_ids_for_doctrine,
)

PATH = "{int:doctrine_id}/change-requests"
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


def _doctrine_payload(doctrine: EveDoctrine, body: DoctrineChangeRequestBody):
    composition = {
        role: sorted(set(getattr(body.composition, role)))
        for role in DOCTRINE_FITTING_ROLES
    }
    return {
        "name": body.name.strip(),
        "type": body.type,
        "description": body.description,
        "retired": (
            doctrine.retired if body.retired is None else body.retired
        ),
        "composition": composition,
        "location_ids": location_ids_for_doctrine(doctrine),
    }


def _validation_problem(doctrine: EveDoctrine, proposed: dict) -> str | None:
    if not proposed["name"]:
        return "Name is required."
    if proposed["type"] not in dict(EveDoctrine.type_choices):
        return "Unknown doctrine type."
    taken = EveDoctrine.objects.filter(name=proposed["name"])
    if taken.exclude(pk=doctrine.pk).exists():
        return "A doctrine with that name already exists."
    all_ids = {i for ids in proposed["composition"].values() for i in ids}
    if EveFitting.objects.filter(pk__in=all_ids).count() != len(all_ids):
        return "Unknown fitting in the composition."
    if not doctrine_state_changed(doctrine, proposed):
        return "Nothing changed."
    return None


def post_doctrine_change_request(
    request, doctrine_id: int, payload: DoctrineChangeRequestBody
):
    if not can_edit_doctrines(request.user):
        return 403, {"detail": "You cannot propose doctrine changes"}
    # all_objects so a removed doctrine can be brought back by id.
    doctrine = EveDoctrine.all_objects.filter(id=doctrine_id).first()
    if not doctrine:
        return 404, {"detail": "Doctrine not found"}

    proposed = _doctrine_payload(doctrine, payload)
    problem = _validation_problem(doctrine, proposed)
    if problem:
        return 400, {"detail": problem}

    diffs = doctrine_diffs(doctrine, proposed)
    if payload.preview:
        return {"diffs": diffs}
    if change_tier_for(
        doctrine, proposed
    ) is not None and pending_doctrine_request_exists(doctrine):
        return 409, {"detail": "A pending change request already exists."}
    try:
        change_request = submit_doctrine_change_request(
            doctrine, proposed, request.user, note=payload.note
        )
    except PermissionError as exc:
        return 403, {"detail": str(exc)}
    except ValueError as exc:
        return 409, {"detail": str(exc)}
    if change_request is None:
        # Experimental doctrines need no review: the edit applied directly.
        return {"diffs": diffs, "applied": True}
    return {
        "diffs": diffs,
        "request": serialize_request(request.user, "doctrine", change_request),
    }
