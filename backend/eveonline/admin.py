from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.contrib import messages
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
    EveCharacterSkill,
)
from .helpers.characters import user_primary_character
from .tasks import update_corporation
from groups.helpers import (
    ensure_corporation_groups_for_corp,
    offboard_corporation_groups,
)

# Register your models here.
admin.site.register(EveSkillset)
admin.site.register(EveAlliance)
admin.site.register(EveTag)
admin.site.register(EveCharacterTag)
admin.site.unregister(CallbackRedirect)
admin.site.unregister(Token)
admin.site.unregister(Scope)


def refresh_corporations_action(modeladmin, request, queryset):
    """Queue refresh (update) for selected corporations."""
    for corp in queryset:
        update_corporation.delay(corp.corporation_id)
    n = queryset.count()
    modeladmin.message_user(
        request,
        f"Refresh queued for {n} corporation(s).",
        level=messages.SUCCESS,
    )


refresh_corporations_action.short_description = "Refresh selected corporations"


@admin.register(EveCorporation)
class EveCorporationAdmin(admin.ModelAdmin):
    """
    Custom admin to make editing corporations easier
    """

    list_display = (
        "name",
        "ticker",
        "alliance",
        "generate_corporation_groups",
    )
    search_fields = ("name", "ticker")
    list_filter = ("alliance", "generate_corporation_groups")
    filter_horizontal = ("directors", "recruiters", "stewards")
    actions = [refresh_corporations_action]
    change_form_template = "admin/eveonline/evecorporation/change_form.html"

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                "<path:object_id>/refresh/",
                self.admin_site.admin_view(self.refresh_corporation_view),
                name="eveonline_evecorporation_refresh",
            ),
        ]
        return extra + urls

    def refresh_corporation_view(self, request, object_id):
        """Queue a refresh for this corporation and redirect back to change form."""
        corp = EveCorporation.objects.get(pk=object_id)
        update_corporation.delay(corp.corporation_id)
        self.message_user(
            request,
            f"Refresh queued for corporation “{corp.name}”.",
            level=messages.SUCCESS,
        )
        url = reverse(
            "admin:eveonline_evecorporation_change",
            args=[object_id],
            current_app=self.admin_site.name,
        )
        return HttpResponseRedirect(url)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id != "add":
            extra_context["refresh_url"] = reverse(
                "admin:eveonline_evecorporation_refresh",
                args=[object_id],
                current_app=self.admin_site.name,
            )
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if change and obj.pk:
            old = EveCorporation.objects.get(pk=obj.pk)
            if (
                old.generate_corporation_groups
                and not obj.generate_corporation_groups
            ):
                offboard_corporation_groups(old)
        super().save_model(request, obj, form, change)
        if obj.generate_corporation_groups and obj.ticker:
            ensure_corporation_groups_for_corp(obj)


@admin.register(EveCharacter)
class EveCharacterAdmin(admin.ModelAdmin):
    """
    Custom admin to make editing characters easier
    """

    list_display = (
        "character_name",
        "corporation_id",
        "alliance_id",
        "primary_eve_character",
    )
    search_fields = ("character_name",)
    list_filter = ("corporation_id", "alliance_id")

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
    search_fields = ("location_name", "short_name", "solar_system_name")
    list_filter = ("market_active", "freight_active", "staging_active")
    ordering = ("location_name",)


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


@admin.register(EveCharacterSkill)
class EveCharacterSkillAdmin(admin.ModelAdmin):
    """Admin screen for EveCharacterSkill"""

    list_display = (
        "character__character_name",
        "skill_name",
        "skill_level",
    )

    search_fields = ("character__character_name", "skill_name")
