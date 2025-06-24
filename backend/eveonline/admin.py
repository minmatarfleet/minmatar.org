from django.contrib import admin
from esi.models import CallbackRedirect, Scope, Token

from .models import (
    EvePlayer,
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EveSkillset,
    EveTag,
    EveCharacterTag,
    EveLocation,
    EveCharacterAsset,
)
from .helpers.characters import user_primary_character

# Register your models here.
admin.site.register(EveSkillset)
admin.site.register(EveAlliance)
admin.site.register(EveTag)
admin.site.register(EveCharacterTag)
admin.site.unregister(CallbackRedirect)
admin.site.unregister(Token)
admin.site.unregister(Scope)


@admin.register(EveCorporation)
class EveCorporationAdmin(admin.ModelAdmin):
    """
    Custom admin to make editing corporations easier
    """

    list_display = ("name", "ticker", "alliance")
    search_fields = ("name", "ticker")
    list_filter = ("alliance",)


@admin.register(EveCharacter)
class EveCharacterAdmin(admin.ModelAdmin):
    """
    Custom admin to make editing characters easier
    """

    list_display = (
        "character_name",
        "corporation",
        "alliance",
        "primary_eve_character",
    )
    search_fields = ("character_name", "corporation__name")
    list_filter = ("corporation", "alliance")

    def primary_eve_character(self, obj):
        if obj.user:
            return user_primary_character(obj.user)


@admin.register(EvePlayer)
class EvePlayerAdmin(admin.ModelAdmin):
    """Admin screen for EvePlayer entity"""

    list_display = (
        "id",
        "nickname",
        "user__username",
        "primary_character__character_name",
    )
    list_display_links = ("id", "nickname")
    search_fields = (
        "user__username",
        "primary_character__character_name",
        "nickname",
    )

    readonly_fields = ["id", "characters"]

    def characters(self, instance):
        chars = []
        for char in instance.characters():
            chars.append(char.character_name)
        return chars


@admin.register(EveLocation)
class EveLocationAdmin(admin.ModelAdmin):
    """Admin screen for EveLocation entity"""

    list_display = (
        "location_id",
        "location_name",
        "solar_system_name",
        "market_active",
        "freight_active",
        "staging_active",
    )


@admin.register(EveCharacterAsset)
class EveCharacterAssetAdmin(admin.ModelAdmin):
    """Admin screen for EveCharacterAsset entity"""

    list_display = (
        "id",
        "character__character_name",
        "type_name",
        "location_name",
        "item_id",
        "updated",
    )

    search_fields = ("character__character_name", "type_name", "location_name")
