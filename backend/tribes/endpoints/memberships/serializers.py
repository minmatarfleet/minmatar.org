"""Shared serializer helpers for membership endpoints."""

from tribes.endpoints.memberships.schemas import MembershipSchema
from tribes.helpers.requirements import check_character_meets_requirements
from tribes.models import (
    TribeGroupMembership,
    TribeGroupMembershipCharacterHistory,
)


def _character_committed_at(membership_id: int, character_id: int) -> str:
    """
    Return the ISO timestamp when the character was committed (action=added).
    Falls back to an empty string if no history exists.
    """
    h = (
        TribeGroupMembershipCharacterHistory.objects.filter(
            membership_id=membership_id,
            character_id=character_id,
            action=TribeGroupMembershipCharacterHistory.ACTION_ADDED,
        )
        .order_by("at")
        .first()
    )
    return h.at.isoformat() if h else ""


def serialize_membership(
    m: TribeGroupMembership,
    *,
    include_requirement_status: bool = False,
):
    """
    Serialize a TribeGroupMembership to MembershipSchema.

    The character list contains only currently committed characters (the
    current-roster link table).  committed_at is derived from
    TribeGroupMembershipCharacterHistory.

    When include_requirement_status is True, each character gets
    qualifies, missing_skills, missing_assets (for chief view).
    """
    chars = m.characters.select_related("character").all()
    character_list = []
    for c in chars:
        char_data = {
            "id": c.pk,
            "character_id": c.character.character_id,
            "character_name": c.character.character_name,
            "committed_at": _character_committed_at(m.pk, c.character_id),
            "left_at": None,
        }
        if include_requirement_status:
            req_snapshot = check_character_meets_requirements(
                c.character, m.tribe_group
            )
            char_data["qualifies"] = any(
                data["met"] for data in req_snapshot.values()
            )
            char_data["missing_skills"] = any(
                data.get("skill_met") is False
                for data in req_snapshot.values()
            )
            char_data["missing_assets"] = any(
                data.get("asset_met") is False
                for data in req_snapshot.values()
            )
        character_list.append(char_data)

    return MembershipSchema(
        id=m.pk,
        user_id=m.user_id,
        tribe_group_id=m.tribe_group_id,
        tribe_group_name=str(m.tribe_group),
        tribe_id=m.tribe_group.tribe_id,
        status=m.status,
        inactive_reason=m.history_inactive_reason or "",
        requirement_snapshot=m.requirement_snapshot,
        created_at=m.created_at.isoformat(),
        approved_by_id=m.approved_by_id,
        approved_at=m.approved_at.isoformat() if m.approved_at else None,
        left_at=m.left_at.isoformat() if m.left_at else None,
        characters=character_list,
    )
