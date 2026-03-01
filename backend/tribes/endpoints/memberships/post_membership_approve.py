"""POST "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/approve"."""

from django.utils import timezone
from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.memberships.schemas import MembershipSchema
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupMembership

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/approve"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Approve a pending membership (chiefs/elders only).",
    "response": {200: MembershipSchema, 400: dict, 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Memberships"])


def post_membership_approve(
    request, tribe_id: int, group_id: int, membership_id: int
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {
            "detail": "You do not have permission to approve memberships here."
        }

    membership = TribeGroupMembership.objects.filter(
        pk=membership_id, tribe_group=tg
    ).first()
    if not membership:
        return 404, {"detail": "Membership not found."}
    if membership.status != TribeGroupMembership.STATUS_PENDING:
        return 400, {
            "detail": f"Cannot approve a membership with status '{membership.status}'."
        }

    membership.status = TribeGroupMembership.STATUS_APPROVED
    membership.approved_by = request.user
    membership.approved_at = timezone.now()
    membership.save()

    return 200, _serialize(membership)


def _serialize(m: TribeGroupMembership) -> MembershipSchema:
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
            for c in m.characters.filter(left_at__isnull=True).select_related(
                "character"
            )
        ],
    )


router.post(PATH, **ROUTE_SPEC)(post_membership_approve)
