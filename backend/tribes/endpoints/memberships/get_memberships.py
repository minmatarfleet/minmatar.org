"""GET "/{tribe_id}/groups/{group_id}/memberships" - list memberships."""

from typing import List, Optional

from authentication import AuthBearer
from tribes.endpoints.memberships.schemas import MembershipSchema
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupMembership

PATH = "/{tribe_id}/groups/{group_id}/memberships"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List memberships for a tribe group (chiefs/elders see all; members see own).",
    "response": {200: List[MembershipSchema], 403: dict, 404: dict},
    "auth": AuthBearer(),
}


def get_memberships(
    request,
    tribe_id: int,
    group_id: int,
    status: Optional[str] = None,
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    if user_can_manage_group(request.user, tg):
        qs = TribeGroupMembership.objects.filter(tribe_group=tg)
    else:
        qs = TribeGroupMembership.objects.filter(
            tribe_group=tg, user=request.user
        )

    if status:
        qs = qs.filter(status=status)

    qs = qs.select_related("tribe_group__tribe").prefetch_related(
        "characters__character"
    )

    return 200, [
        MembershipSchema(
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
                for c in m.characters.filter(left_at__isnull=True)
            ],
        )
        for m in qs
    ]
