from django.contrib import admin

from eveonline.models import EvePrimaryCharacter

from .models import DiscordUser


# Register your models here.
@admin.register(DiscordUser)
class DiscordUserAdmin(admin.ModelAdmin):
    list_display = ("discord_tag", "nickname", "primary_eve_character")
    search_fields = ("discord_tag", "nickname")

    def primary_eve_character(self, obj):
        user = obj.user
        return EvePrimaryCharacter.objects.filter(
            character__token__user=user
        ).first()
