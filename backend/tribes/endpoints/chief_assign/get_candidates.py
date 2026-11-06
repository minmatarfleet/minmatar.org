"""GET "/chief-candidates?q=" - find a pilot to make chief (superuser)."""

from typing import List

from ninja import Router

from authentication import AuthBearer
from eveonline.helpers.characters.characters import user_primary_character
from eveonline.models import EveCharacter
from tribes.endpoints.chief_assign.schemas import ChiefCandidateSchema

MIN_QUERY = 2
MAX_RESULTS = 12

PATH = "/chief-candidates"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Find pilots to make chief, by any of their characters' names.",
    "response": {200: List[ChiefCandidateSchema], 403: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Chiefs"])


def get_chief_candidates(request, q: str = ""):
    if not request.user.is_superuser:
        return 403, {"detail": "Only superusers can swap a chief."}
    q = (q or "").strip()
    if len(q) < MIN_QUERY:
        return 200, []
    matches = (
        EveCharacter.objects.filter(
            character_name__icontains=q, user__isnull=False
        )
        .select_related("user")
        .order_by("character_name")[: MAX_RESULTS * 4]
    )
    seen = set()
    results = []
    for character in matches:
        user = character.user
        if user.pk in seen:
            continue
        seen.add(user.pk)
        primary = user_primary_character(user) or character
        results.append(
            {
                "user_id": user.pk,
                "character_id": primary.character_id,
                "character_name": primary.character_name,
                "matched_character_name": (
                    character.character_name
                    if character.character_id != primary.character_id
                    else ""
                ),
            }
        )
        if len(results) >= MAX_RESULTS:
            break
    return 200, results


router.get(PATH, **ROUTE_SPEC)(get_chief_candidates)
