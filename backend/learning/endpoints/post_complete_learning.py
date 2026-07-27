"""POST /learnings/{slug}/complete — mark a learning complete and recompute awards."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from learning.helpers import mark_learning_complete
from learning.models import Learning
from learning.schemas import CompleteLearningResponse
from learning.serialization import serialize_award

PATH = "learnings/{slug}/complete"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Mark a learning as complete for the authenticated user.",
    "auth": AuthBearer(),
    "response": {200: CompleteLearningResponse, 404: ErrorResponse},
}


def post_complete_learning(request, slug: str):
    learning = Learning.objects.filter(slug=slug, published=True).first()
    if learning is None:
        return 404, ErrorResponse(detail="Learning not found.")

    _, _, awarded = mark_learning_complete(request.user, learning)
    return CompleteLearningResponse(
        learning_slug=learning.slug,
        completed=True,
        newly_awarded=[serialize_award(a) for a in awarded],
    )
