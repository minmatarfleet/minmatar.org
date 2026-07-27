"""GET /persona/recommendation — suggested persona from primary character."""

from authentication import AuthBearer
from learning.helpers import recommend_persona
from learning.schemas import PersonaRecommendationSchema

PATH = "persona/recommendation"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Recommend a Learning Center persona for the authenticated user.",
    "auth": AuthBearer(),
    "response": {200: PersonaRecommendationSchema},
}


def get_persona_recommendation(request):
    result = recommend_persona(request.user)
    return PersonaRecommendationSchema(
        persona=result["persona"],
        reason_key=result["reason_key"],
        corp_type=result["corp_type"],
    )
