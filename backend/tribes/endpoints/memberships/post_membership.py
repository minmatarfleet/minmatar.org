"""POST "/{tribe_id}/groups/{group_id}/memberships" - apply to a tribe group."""

import logging

from authentication import AuthBearer
from eveonline.models import EveCharacter
from tribes.endpoints.memberships.schemas import (
    ApplyToGroupRequest,
    MembershipSchema,
)
from tribes.endpoints.memberships.serializers import serialize_membership
from tribes.helpers import build_membership_snapshot, user_can_manage_group
from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipCharacterHistory,
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
        user=request.user, tribe_group=tg
    ).first()

    if existing:
        if existing.status in (
            TribeGroupMembership.STATUS_PENDING,
            TribeGroupMembership.STATUS_ACTIVE,
        ):
            return 400, {
                "detail": f"Existing membership in status '{existing.status}' already exists."
            }

        # status == inactive — reset to pending (re-application).
        membership = existing
        snapshot = build_membership_snapshot(
            request.user, tg, payload.character_ids
        )
        membership.status = TribeGroupMembership.STATUS_PENDING
        membership.requirement_snapshot = snapshot
        membership.approved_by = None
        membership.approved_at = None
        membership.left_at = None
        membership.removed_by = None
        membership.history_changed_by = request.user
        membership.save()

        # Clear any stale current-roster links (should be empty after leave,
        # but guard anyway) before attaching the new characters.
        membership.characters.all().delete()
    else:
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
        _, created = TribeGroupMembershipCharacter.objects.get_or_create(
            membership=membership,
            character=character,
        )
        if created:
            TribeGroupMembershipCharacterHistory.objects.create(
                membership=membership,
                character=character,
                action=TribeGroupMembershipCharacterHistory.ACTION_ADDED,
                by=request.user,
            )

    can_manage = user_can_manage_group(request.user, tg)
    return 200, serialize_membership(
        membership,
        include_requirement_status=False,
        include_characters=can_manage,
    )
