"""PATCH "/{tribe_id}" - rename, archive or restore a tribe."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints import structure_errors
from tribes.endpoints.structure_schemas import StructurePatchRequest
from tribes.endpoints.tribes.schemas import TribeSchema
from tribes.endpoints.tribes.serializers import serialize_tribe
from tribes.helpers.structure import update_tribe
from tribes.models import Tribe

PATH = "/{tribe_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Rename, archive or restore a tribe.",
    "description": (
        "Needs tribes.structure.manage. A rename renames the linked auth "
        "group and Discord role; the slug stays."
    ),
    "response": {
        200: TribeSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        502: ErrorResponse,
    },
    "auth": AuthBearer(),
}


def patch_tribe(request, tribe_id: int, payload: StructurePatchRequest):
    tribe = Tribe.objects.select_related("group").filter(pk=tribe_id).first()
    if tribe is None:
        return 404, ErrorResponse(detail="Tribe not found.")
    error, tribe = structure_errors.run(
        lambda: update_tribe(
            request.user,
            tribe,
            name=payload.name,
            is_active=payload.is_active,
        )
    )
    if error:
        return error
    return 200, serialize_tribe(tribe, request_user=request.user)
