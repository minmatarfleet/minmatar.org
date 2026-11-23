"""PATCH "/{tribe_id}/groups/{group_id}" - rename, archive or restore."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints import structure_errors
from tribes.endpoints.groups.schemas import TribeGroupSchema
from tribes.endpoints.groups.serializers import serialize_tribe_group
from tribes.endpoints.structure_schemas import StructurePatchRequest
from tribes.helpers.structure import update_tribe_group
from tribes.models import TribeGroup

PATH = "/{tribe_id}/groups/{group_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Rename, archive or restore a tribe group.",
    "description": (
        "Needs tribes.structure.manage. A rename renames the linked auth "
        "group and Discord role; the code stays."
    ),
    "response": {
        200: TribeGroupSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        502: ErrorResponse,
    },
    "auth": AuthBearer(),
}


def patch_tribe_group(
    request, tribe_id: int, group_id: int, payload: StructurePatchRequest
):
    tribe_group = (
        TribeGroup.objects.select_related("tribe", "group")
        .filter(pk=group_id, tribe_id=tribe_id)
        .first()
    )
    if tribe_group is None:
        return 404, ErrorResponse(detail="TribeGroup not found.")
    error, tribe_group = structure_errors.run(
        lambda: update_tribe_group(
            request.user,
            tribe_group,
            name=payload.name,
            is_active=payload.is_active,
        )
    )
    if error:
        return error
    return 200, serialize_tribe_group(tribe_group, request_user=request.user)
