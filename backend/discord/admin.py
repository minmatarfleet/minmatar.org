from django.contrib import admin, messages

from eveonline.helpers.characters import user_primary_character

from .forms import DiscordChannelAdminForm
from .guilds import sync_discord_guilds
from .models import DiscordChannel, DiscordGuild, DiscordUser, DiscordRole


@admin.register(DiscordUser)
class DiscordUserAdmin(admin.ModelAdmin):
    list_display = ("discord_tag", "nickname", "primary_eve_character", "id")
    search_fields = ("discord_tag", "nickname", "id")

    def primary_eve_character(self, obj):
        return user_primary_character(obj.user)


@admin.register(DiscordRole)
class DiscordRoleAdmin(admin.ModelAdmin):
    list_display = ("role_id", "name")
    search_fields = ("role_id", "name")


@admin.register(DiscordGuild)
class DiscordGuildAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "guild_id",
        "is_primary",
        "is_active",
        "last_seen_at",
        "updated_at",
    )
    list_filter = ("is_primary", "is_active")
    search_fields = ("name", "guild_id")
    readonly_fields = (
        "guild_id",
        "name",
        "is_primary",
        "is_active",
        "last_seen_at",
        "created_at",
        "updated_at",
    )
    actions = ("sync_guilds",)

    def has_add_permission(self, request):
        return False

    @admin.action(description="Sync guilds from Discord")
    def sync_guilds(self, request, queryset):
        del queryset
        try:
            count = sync_discord_guilds()
        except Exception as error:
            self.message_user(
                request,
                f"Failed to sync Discord guilds: {error}",
                level=messages.ERROR,
            )
            return
        self.message_user(
            request,
            f"Synced {count} guild(s) from Discord.",
            level=messages.SUCCESS,
        )


@admin.register(DiscordChannel)
class DiscordChannelAdmin(admin.ModelAdmin):
    form = DiscordChannelAdminForm
    list_display = (
        "name",
        "guild",
        "channel_type",
        "track_voice_activity",
        "channel_id",
        "updated_at",
    )
    list_filter = ("guild", "channel_type", "track_voice_activity")
    search_fields = ("name", "channel_id", "guild__name")
    readonly_fields = (
        "channel_id",
        "name",
        "channel_type",
        "created_at",
        "updated_at",
    )

    def get_fields(self, request, obj=None):
        if obj:
            return (
                "guild",
                "channel_id",
                "name",
                "channel_type",
                "track_voice_activity",
                "created_at",
                "updated_at",
            )
        return ("discord_channel_pick", "track_voice_activity")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if (
            not change
            and not DiscordGuild.objects.filter(is_active=True).exists()
        ):
            messages.warning(
                request,
                "No active Discord guilds are synced yet. Run “Sync guilds from Discord”.",
            )
