"""GET "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/characters"."""

from typing import List

from authentication import AuthBearer
from tribes.endpoints.memberships.schemas import MembershipCharacterSchema
from tribes.helpers import user_can_manage_group
from tribes.helpers.requirements import check_character_meets_requirements
from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacterHistory,
)

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/characters"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List characters currently committed to a membership.",
    "response": {200: List[MembershipCharacterSchema], 403: dict, 404: dict},
    "auth": AuthBearer(),
}


def get_membership_characters(
    request, tribe_id: int, group_id: int, membership_id: int
):
    tg = (
        TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id)
        .prefetch_related(
            "requirements__asset_types__eve_type",
            "requirements__qualifying_skills__eve_type",
        )
        .first()
    )
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    membership = TribeGroupMembership.objects.filter(
        pk=membership_id, tribe_group=tg
    ).first()
    if not membership:
        return 404, {"detail": "Membership not found."}

    is_own = membership.user_id == request.user.pk
    if not is_own and not user_can_manage_group(request.user, tg):
        return 403, {"detail": "Access denied."}

    chars = membership.characters.select_related("character").all()

    # Derive committed_at from character history.
    history_map = {
        h.character_id: h.at
        for h in TribeGroupMembershipCharacterHistory.objects.filter(
            membership=membership,
            action=TribeGroupMembershipCharacterHistory.ACTION_ADDED,
        ).order_by("at")
    }

    result = []
    for c in chars:
        h_at = history_map.get(c.character_id)
        qualifies = None
        missing_skills = None
        missing_assets = None
        if user_can_manage_group(request.user, tg):
            req_snapshot = check_character_meets_requirements(c.character, tg)
            qualifies = any(data["met"] for data in req_snapshot.values())
            missing_skills = any(
                data.get("skill_met") is False
                for data in req_snapshot.values()
            )
            missing_assets = any(
                data.get("asset_met") is False
                for data in req_snapshot.values()
            )
        result.append(
            MembershipCharacterSchema(
                id=c.pk,
                character_id=c.character.character_id,
                character_name=c.character.character_name,
                committed_at=h_at.isoformat() if h_at else None,
                left_at=None,
                qualifies=qualifies,
                missing_skills=missing_skills,
                missing_assets=missing_assets,
            )
        )
    return 200, result
