"""Delete the Market tribe group and its auth group.

Market stocking lives on Market ops. Active members keep hub management and
produced-order submit via eveonline.change_evelocation. A help category linked
to the group is unlinked and hidden so existing tickets can stay.

Cascades remove memberships (and their history), requirements, invitations,
events and ranks. Posts, orders and fleets only lose their link. Members
whose only Supply group this was are taken off the Supply auth group. The
Discord role itself is not touched; remove it in Discord by hand.
"""

from django.db import migrations

from discord.sync_context import disable_discord_group_sync

CODE = "supply.market"
ACTIVE = "active"
LOCATION_PERMISSION = "change_evelocation"


def _grant_location_permission(apps, tribe_group):
    """Keep Market ops access for people who held it through this group."""
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("auth", "User")
    Membership = apps.get_model("tribes", "TribeGroupMembership")

    permission = Permission.objects.filter(
        content_type__app_label="eveonline",
        content_type__model="evelocation",
        codename=LOCATION_PERMISSION,
    ).first()
    if permission is None:
        return

    user_ids = Membership.objects.filter(
        tribe_group=tribe_group,
        status=ACTIVE,
    ).values_list("user_id", flat=True)
    for user in User.objects.filter(pk__in=user_ids):
        user.user_permissions.add(permission)


def _drop_supply_role_when_only_group(apps, tribe_group):
    """Match an inactive membership: leave Supply only with no other group."""
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")
    Membership = apps.get_model("tribes", "TribeGroupMembership")

    tribe_auth_id = tribe_group.tribe.group_id
    if not tribe_auth_id:
        return
    tribe_auth = Group.objects.filter(pk=tribe_auth_id).first()
    if tribe_auth is None:
        return

    user_ids = Membership.objects.filter(tribe_group=tribe_group).values_list(
        "user_id", flat=True
    )
    for user in User.objects.filter(pk__in=user_ids):
        still_active = (
            Membership.objects.filter(
                user=user,
                status=ACTIVE,
                tribe_group__tribe_id=tribe_group.tribe_id,
            )
            .exclude(tribe_group_id=tribe_group.pk)
            .exists()
        )
        if still_active:
            continue
        if user.groups.filter(pk=tribe_auth.pk).exists():
            user.groups.remove(tribe_auth)


def delete_market_tribe_group(apps, schema_editor):
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    TribeGroupRank = apps.get_model("tribes", "TribeGroupRank")
    Group = apps.get_model("auth", "Group")
    HelpRequestCategory = apps.get_model("help_tickets", "HelpRequestCategory")

    with disable_discord_group_sync():
        for tribe_group in list(TribeGroup.objects.filter(code=CODE)):
            _grant_location_permission(apps, tribe_group)
            _drop_supply_role_when_only_group(apps, tribe_group)
            rank_group_ids = list(
                TribeGroupRank.objects.filter(
                    tribe_group=tribe_group,
                    group_id__isnull=False,
                ).values_list("group_id", flat=True)
            )
            HelpRequestCategory.objects.filter(
                tribe_group_id=tribe_group.pk
            ).update(tribe_group=None, is_active=False)
            auth_group_id = tribe_group.group_id
            tribe_group.delete()
            group_ids = [pk for pk in [auth_group_id, *rank_group_ids] if pk]
            if group_ids:
                Group.objects.filter(pk__in=group_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0049_tribe_discord_guild"),
        ("help_tickets", "0003_category_code_help_text"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(
            delete_market_tribe_group, migrations.RunPython.noop
        ),
    ]
