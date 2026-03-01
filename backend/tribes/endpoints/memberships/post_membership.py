"""POST "/{tribe_id}/groups/{group_id}/memberships" - apply to a tribe group."""

import logging

from authentication import AuthBearer
from eveonline.models import EveCharacter
from tribes.endpoints.memberships.schemas import (
    ApplyToGroupRequest,
    MembershipSchema,
)
from tribes.helpers import build_membership_snapshot
from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
)

logger = logging.getLogger(__name__)

PATH = "/{tribe_id}/groups/{group_id}/memberships"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Apply to join a tribe group.",
    "response": {200: MembershipSchema, 400: dict, 404: dict},
    "auth": AuthBearer(),
}


def post_membership(
    request, tribe_id: int, group_id: int, payload: ApplyToGroupRequest
):
    tg = TribeGroup.objects.filter(
        pk=group_id, tribe_id=tribe_id, is_active=True
    ).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    existing = TribeGroupMembership.objects.filter(
        user=request.user,
        tribe_group=tg,
        status__in=[
            TribeGroupMembership.STATUS_PENDING,
            TribeGroupMembership.STATUS_APPROVED,
        ],
    ).first()
    if existing:
        return 400, {
            "detail": f"Existing membership in status '{existing.status}' already exists."
        }

    snapshot = build_membership_snapshot(
        request.user, tg, payload.character_ids
    )
    membership = TribeGroupMembership.objects.create(
        user=request.user,
        tribe_group=tg,
        status=TribeGroupMembership.STATUS_PENDING,
        requirement_snapshot=snapshot,
    )

    for char_id in payload.character_ids:
        character = EveCharacter.objects.filter(
            character_id=char_id, user=request.user
        ).first()
        if not character:
            logger.warning(
                "Character character_id=%s not found for user %s; skipping commit.",
                char_id,
                request.user,
            )
            continue
        TribeGroupMembershipCharacter.objects.get_or_create(
            membership=membership,
            character=character,
        )

    return 200, _serialize(membership)


def _serialize(m: TribeGroupMembership) -> MembershipSchema:
    chars = TribeGroupMembershipCharacter.objects.filter(
        membership=m, left_at__isnull=True
    ).select_related("character")
    return MembershipSchema(
        id=m.pk,
        user_id=m.user_id,
        tribe_group_id=m.tribe_group_id,
        tribe_group_name=str(m.tribe_group),
        tribe_id=m.tribe_group.tribe_id,
        status=m.status,
        requirement_snapshot=m.requirement_snapshot,
        created_at=m.created_at.isoformat(),
        approved_by_id=m.approved_by_id,
        approved_at=m.approved_at.isoformat() if m.approved_at else None,
        left_at=m.left_at.isoformat() if m.left_at else None,
        characters=[
            {
                "id": c.pk,
                "character_id": c.character.character_id,
                "character_name": c.character.character_name,
                "committed_at": c.committed_at.isoformat(),
                "left_at": c.left_at.isoformat() if c.left_at else None,
            }
            for c in chars
        ],
    )
