"""Custom tribe group admin views."""

from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import reverse

from tribes.helpers.admin_permissions import (
    VIEW_TRIBE_GROUPS,
    require_tribes_admin_view,
)
from tribes.helpers.admin_urls import add_url, changelist_url
from tribes.helpers.admin_views import (
    get_tribe_group_or_redirect,
    render_tribe_group_view,
)
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupActivityRecord,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipCharacterHistory,
    TribeGroupMembershipHistory,
)


def _build_hub_sections(tribe_group: TribeGroup) -> dict:
    group_id = tribe_group.pk
    membership_filter = {"membership__tribe_group__id__exact": group_id}
    activity_record_filter = {
        "tribe_group_activity__tribe_group__id__exact": group_id
    }
    group_filter = {"tribe_group__id__exact": group_id}

    return {
        "settings": {
            "edit_url": reverse(
                "admin:tribes_tribegroup_change", args=[group_id]
            ),
        },
        "ranks": {
            "count": tribe_group.ranks.count(),
            "list_url": changelist_url("tribegrouprank", **group_filter),
            "add_url": add_url("tribegrouprank", tribe_group=group_id),
        },
        "requirements": {
            "count": tribe_group.requirements.count(),
            "list_url": changelist_url(
                "tribegrouprequirement", **group_filter
            ),
            "add_url": add_url("tribegrouprequirement", tribe_group=group_id),
        },
        "memberships": {
            "count": tribe_group.memberships.count(),
            "list_url": changelist_url("tribegroupmembership", **group_filter),
            "add_url": add_url("tribegroupmembership", tribe_group=group_id),
        },
        "membership_characters": {
            "count": TribeGroupMembershipCharacter.objects.filter(
                membership__tribe_group_id=group_id
            ).count(),
            "list_url": changelist_url(
                "tribegroupmembershipcharacter", **membership_filter
            ),
            "add_url": add_url("tribegroupmembershipcharacter"),
        },
        "membership_history": {
            "count": TribeGroupMembershipHistory.objects.filter(
                membership__tribe_group_id=group_id
            ).count(),
            "list_url": changelist_url(
                "tribegroupmembershiphistory", **membership_filter
            ),
        },
        "character_history": {
            "count": TribeGroupMembershipCharacterHistory.objects.filter(
                membership__tribe_group_id=group_id
            ).count(),
            "list_url": changelist_url(
                "tribegroupmembershipcharacterhistory",
                **membership_filter,
            ),
        },
        "activities": {
            "count": tribe_group.activities.count(),
            "list_url": changelist_url("tribegroupactivity", **group_filter),
            "add_url": add_url("tribegroupactivity", tribe_group=group_id),
        },
        "activity_records": {
            "count": TribeGroupActivityRecord.objects.filter(
                tribe_group_activity__tribe_group_id=group_id
            ).count(),
            "list_url": changelist_url(
                "tribegroupactivityrecord", **activity_record_filter
            ),
            "add_url": add_url("tribegroupactivityrecord"),
        },
    }


def tribes_view(request):
    require_tribes_admin_view(request.user)
    tribes = Tribe.objects.select_related("chief").order_by("name")
    tribe_rows = [
        {
            "tribe": tribe,
            "edit_url": reverse("admin:tribes_tribe_change", args=[tribe.pk]),
        }
        for tribe in tribes
    ]
    groups = TribeGroup.objects.select_related("tribe", "chief").order_by(
        "tribe__name", "name"
    )
    group_rows = [
        {
            "tribe_group": tribe_group,
            "hub_url": reverse(
                "admin:tribes_group_hub", args=[tribe_group.pk]
            ),
        }
        for tribe_group in groups
    ]
    context = {
        **admin.site.each_context(request),
        "title": "Tribes",
        "tribe_rows": tribe_rows,
        "group_rows": group_rows,
        "add_tribe_url": reverse("admin:tribes_tribe_add"),
        "add_group_url": reverse("admin:tribes_tribegroup_add"),
    }
    return TemplateResponse(request, "admin/tribes/tribes_list.html", context)


def tribe_group_hub_view(request, group_id):
    tribe_group, redirect = get_tribe_group_or_redirect(request, group_id)
    if redirect:
        return redirect
    return render_tribe_group_view(
        request,
        tribe_group=tribe_group,
        title=f"Tribe group — {tribe_group.name}",
        template_name="admin/tribes/group_hub.html",
        context={"sections": _build_hub_sections(tribe_group)},
        view_perm=VIEW_TRIBE_GROUPS,
    )
