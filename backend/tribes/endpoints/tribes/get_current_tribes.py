"""GET "/current" - tribes the current user is a member of."""

from typing import List

from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.tribes.schemas import TribeSchema
from tribes.models import Tribe, TribeGroupMembership

PATH = "/current"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Tribes the current user is a member of (via any TribeGroup).",
    "response": {200: List[TribeSchema]},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes"])


def get_current_tribes(request):
    tribe_ids = (
        TribeGroupMembership.objects.filter(
            user=request.user, status=TribeGroupMembership.STATUS_ACTIVE
        )
        .values_list("tribe_group__tribe_id", flat=True)
        .distinct()
    )
    result = []
    for tribe in Tribe.objects.filter(pk__in=tribe_ids, is_active=True):
        active_groups = tribe.groups.filter(is_active=True)
        total_members = (
            TribeGroupMembership.objects.filter(
                tribe_group__tribe=tribe,
                status=TribeGroupMembership.STATUS_ACTIVE,
            )
            .values("user")
            .distinct()
            .count()
        )
        result.append(
            TribeSchema(
                id=tribe.pk,
                name=tribe.name,
                slug=tribe.slug,
                description=tribe.description,
                content=tribe.content,
                image_url=tribe.image_url,
                banner_url=tribe.banner_url,
                discord_channel_id=tribe.discord_channel_id,
                chief_id=tribe.chief_id,
                is_active=tribe.is_active,
                group_count=active_groups.count(),
                total_member_count=total_members,
            )
        )
    return result


router.get(PATH, **ROUTE_SPEC)(get_current_tribes)
