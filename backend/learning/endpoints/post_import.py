"""POST /import — merge anonymous learning progress into the authenticated user."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from learning.helpers import import_learning_progress
from learning.models import Persona
from learning.schemas import ImportRequest, ImportResponse
from learning.serialization import serialize_award

PATH = "import"
METHOD = "post"
ROUTE_SPEC = {
    "summary": (
        "Union-merge anonymous Learning Center progress into the "
        "authenticated user's records."
    ),
    "auth": AuthBearer(),
    "response": {200: ImportResponse, 400: ErrorResponse},
}


def post_import(request, payload: ImportRequest):
    persona = (payload.persona or "").strip() or None
    if persona is not None and persona not in Persona.values:
        return 400, ErrorResponse(
            detail="persona must be alliance, militia, or other.",
        )

    result = import_learning_progress(
        user=request.user,
        completed_slugs=payload.completed_learning_slugs or [],
        persona=persona,
    )
    return ImportResponse(
        imported_slugs=result["imported_slugs"],
        persona=result["persona"],
        completed_learning_slugs=result["completed_slugs"],
        awards=[serialize_award(a) for a in result["awards"]],
    )
