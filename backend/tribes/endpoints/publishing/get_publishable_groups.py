"""GET "/publishable-groups" - groups the viewer may publish as."""

from typing import List

from django.db.models import Count, Q
from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.publishing.schemas import (
    PublishableGroupSchema,
    PublishingKind,
)
from tribes.helpers.publishing import host_group_ref, publishable_groups
from tribes.models import TribeGroup, TribeGroupMembership

PATH = "/publishable-groups"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Tribe groups the viewer may post, schedule fleets or "
    "create events as.",
    "response": {200: List[PublishableGroupSchema]},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Publishing"])


def get_publishable_groups(request, kind: PublishingKind):
    groups = publishable_groups(request.user, kind.value)
    counts = dict(
        TribeGroup.objects.filter(pk__in=[g.pk for g in groups])
        .annotate(
            active=Count(
                "memberships",
                filter=Q(
                    memberships__status=TribeGroupMembership.STATUS_ACTIVE
                ),
            )
        )
        .values_list("pk", "active")
    )
    return 200, [
        PublishableGroupSchema(
            **host_group_ref(group),
            member_count=counts.get(group.pk, 0),
            allow_alliance_posts=group.allow_alliance_posts,
            allow_open_fleets=group.allow_open_fleets,
        )
        for group in groups
    ]


router.get(PATH, **ROUTE_SPEC)(get_publishable_groups)
