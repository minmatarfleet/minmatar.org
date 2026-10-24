"""GET "/{tribe_id}/groups/{group_id}/invitations/candidates" - pilot search."""

from typing import List

from ninja import Router

from authentication import AuthBearer
from eveonline.helpers.characters.characters import user_primary_character
from eveonline.models import EveCharacter
from tribes.endpoints.invitations.schemas import InvitationCandidateSchema
from tribes.helpers import user_can_manage_group
from tribes.helpers.invitations import invite_blocker
from tribes.models import TribeGroup

MIN_QUERY = 2
MAX_RESULTS = 12

PATH = "/{tribe_id}/groups/{group_id}/invitations/candidates"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Find pilots to invite, by any of their characters' names.",
    "response": {
        200: List[InvitationCandidateSchema],
        403: dict,
        404: dict,
    },
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Invitations"])


def get_invitation_candidates(
    request, tribe_id: int, group_id: int, q: str = ""
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {"detail": "Only people who manage this group can invite."}

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
        blocker = invite_blocker(user, tg)
        code, detail = blocker if blocker else (None, {})
        when = detail.get("since") or detail.get("until")
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
                "blocker": code,
                "membership_id": detail.get("membership_id"),
                "blocker_date": when.isoformat() if when else None,
            }
        )
        if len(results) >= MAX_RESULTS:
            break
    return 200, results


router.get(PATH, **ROUTE_SPEC)(get_invitation_candidates)
