"""PUT /persona — set or confirm the user's Learning Center persona."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from learning.helpers import set_persona
from learning.models import Persona
from learning.schemas import PersonaRequest, PersonaResponse

PATH = "persona"
METHOD = "put"
ROUTE_SPEC = {
    "summary": "Set the authenticated user's Learning Center persona.",
    "auth": AuthBearer(),
    "response": {200: PersonaResponse, 400: ErrorResponse},
}


def put_persona(request, payload: PersonaRequest):
    persona = (payload.persona or "").strip()
    if persona not in Persona.values:
        return 400, ErrorResponse(
            detail="persona must be alliance, militia, or other.",
        )
    pref = set_persona(request.user, persona, confirmed=True)
    return PersonaResponse(
        persona=pref.persona,
        confirmed=pref.persona_confirmed_at is not None,
    )
