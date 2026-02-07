"""Custom admin for auth Group so deletion uses offboard_group and deletes Discord role."""

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist

from discord.client import DiscordClient

from .helpers import offboard_group

discord = DiscordClient()


def delete_discord_role_for_group(group):
    """If this group has a linked Discord role, delete it on Discord."""
    try:
        discord_role = group.discord_group
        discord.delete_role(discord_role.role_id)
    except ObjectDoesNotExist:
        pass


# Unregister default Group admin so we can replace it with our custom delete behavior.
admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin):
    """Group admin that deletes without m2m signal and deletes the Discord role."""

    def delete_model(self, request, obj):
        delete_discord_role_for_group(obj)
        self.log_deletion(request, obj, str(obj))
        offboard_group(obj.id)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            delete_discord_role_for_group(obj)
            self.log_deletion(request, obj, str(obj))
            offboard_group(obj.id)
