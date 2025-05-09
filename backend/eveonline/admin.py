from django.contrib import admin
from esi.models import CallbackRedirect, Scope, Token

from .models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EveSkillset,
    EveTag,
    EveCharacterTag,
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
