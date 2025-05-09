from django.contrib import admin

from eveonline.helpers.characters import user_primary_character

from .models import DiscordUser


# Register your models here.
@admin.register(DiscordUser)
class DiscordUserAdmin(admin.ModelAdmin):
    list_display = ("discord_tag", "nickname", "primary_eve_character")
    search_fields = ("discord_tag", "nickname")

    def primary_eve_character(self, obj):
        return user_primary_character(obj.user)
