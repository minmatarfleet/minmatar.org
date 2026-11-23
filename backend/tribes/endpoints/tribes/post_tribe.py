"""POST "" - create a tribe and its linked auth group (Discord role)."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints import structure_errors
from tribes.endpoints.structure_schemas import TribeCreateRequest
from tribes.endpoints.tribes.schemas import TribeSchema
from tribes.endpoints.tribes.serializers import serialize_tribe
from tribes.helpers.structure import create_tribe

PATH = ""
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Create a tribe; its auth group and Discord role are made too.",
    "description": "Needs tribes.structure.manage.",
    "response": {
        201: TribeSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        502: ErrorResponse,
    },
    "auth": AuthBearer(),
}


def post_tribe(request, payload: TribeCreateRequest):
    error, tribe = structure_errors.run(
        lambda: create_tribe(
            request.user,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
        )
    )
    if error:
        return error
    return 201, serialize_tribe(tribe, request_user=request.user)
