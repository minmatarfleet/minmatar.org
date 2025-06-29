from django.contrib import admin

from eveonline.helpers.characters import user_primary_character

from .models import DiscordUser, DiscordRole


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
