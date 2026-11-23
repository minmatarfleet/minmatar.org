"""POST "/{tribe_id}/groups" - create a group and its linked auth group."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints import structure_errors
from tribes.endpoints.groups.schemas import TribeGroupSchema
from tribes.endpoints.groups.serializers import serialize_tribe_group
from tribes.endpoints.structure_schemas import TribeGroupCreateRequest
from tribes.helpers.structure import create_tribe_group
from tribes.models import Tribe

PATH = "/{tribe_id}/groups"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Create a tribe group; its auth group and Discord role too.",
    "description": (
        "Needs tribes.structure.manage. The code is {tribe slug}.{name} and "
        "never changes."
    ),
    "response": {
        201: TribeGroupSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        502: ErrorResponse,
    },
    "auth": AuthBearer(),
}


def post_tribe_group(request, tribe_id: int, payload: TribeGroupCreateRequest):
    tribe = Tribe.objects.filter(pk=tribe_id).first()
    if tribe is None:
        return 404, ErrorResponse(detail="Tribe not found.")
    error, tribe_group = structure_errors.run(
        lambda: create_tribe_group(
            request.user,
            tribe,
            name=payload.name,
            description=payload.description,
        )
    )
    if error:
        return error
    return 201, serialize_tribe_group(tribe_group, request_user=request.user)
