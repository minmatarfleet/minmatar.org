from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.contrib import messages
from esi.models import CallbackRedirect, Scope, Token

from .models import (
    EvePlayer,
    EveAlliance,
    EveCharacter,
    EveCharacterBlueprint,
    EveCharacterContract,
    EveCharacterIndustryJob,
    EveCharacterMiningEntry,
    EveCharacterPlanet,
    EveCharacterPlanetOutput,
    EveCorporation,
    EveCorporationBlueprint,
    EveCorporationContract,
    EveCorporationIndustryJob,
    EveSkillset,
    EveTag,
    EveCharacterTag,
    EveLocation,
    EveCharacterAsset,
    EveCharacterSkill,
    EveUniverseSchematic,
)
from .helpers.characters import user_primary_character
from .tasks import update_corporation
from groups.helpers import (
    ensure_corporation_groups_for_corp,
    offboard_corporation_groups,
)

admin.site.unregister(CallbackRedirect)
admin.site.unregister(Token)
admin.site.unregister(Scope)


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------


@admin.register(EvePlayer)
class EvePlayerAdmin(admin.ModelAdmin):
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
        return [c.character_name for c in instance.characters()]


@admin.register(EveCharacter)
class EveCharacterAdmin(admin.ModelAdmin):
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


@admin.register(EveCharacterAsset)
class EveCharacterAssetAdmin(admin.ModelAdmin):
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
    list_display = (
        "character__character_name",
        "skill_name",
        "skill_level",
    )
    search_fields = ("character__character_name", "skill_name")


admin.site.register(EveSkillset)
admin.site.register(EveTag)
admin.site.register(EveCharacterTag)


@admin.register(EveCharacterContract)
class EveCharacterContractAdmin(admin.ModelAdmin):
    list_display = (
        "contract_id",
        "character",
        "type",
        "status",
        "price",
        "date_issued",
        "date_expired",
    )
    list_filter = ("type", "status")
    search_fields = ("contract_id", "character__character_name")
    readonly_fields = ("updated_at",)
    autocomplete_fields = ("character",)
    date_hierarchy = "date_issued"


@admin.register(EveCharacterIndustryJob)
class EveCharacterIndustryJobAdmin(admin.ModelAdmin):
    list_display = (
        "job_id",
        "character",
        "activity_id",
        "blueprint_type_id",
        "status",
        "runs",
        "start_date",
        "end_date",
        "updated_at",
    )
    list_filter = ("status", "activity_id", "character")
    search_fields = ("job_id", "character__character_name")
    readonly_fields = ("updated_at",)
    autocomplete_fields = ("character",)


@admin.register(EveCharacterBlueprint)
class EveCharacterBlueprintAdmin(admin.ModelAdmin):
    list_display = (
        "item_id",
        "character",
        "type_id",
        "location_id",
        "location_flag",
        "material_efficiency",
        "time_efficiency",
        "quantity",
        "runs",
        "updated_at",
    )
    list_filter = ("character", "location_flag")
    search_fields = ("character__character_name", "item_id", "type_id")
    readonly_fields = ("updated_at",)
    autocomplete_fields = ("character",)


@admin.register(EveCharacterMiningEntry)
class EveCharacterMiningEntryAdmin(admin.ModelAdmin):
    list_display = (
        "character",
        "eve_type",
        "quantity",
        "date",
        "solar_system_id",
    )
    list_filter = ("date",)
    search_fields = (
        "character__character_name",
        "eve_type__name",
    )
    autocomplete_fields = ("character",)
    date_hierarchy = "date"
    ordering = ("-date",)


class EveCharacterPlanetOutputInline(admin.TabularInline):
    model = EveCharacterPlanetOutput
    extra = 0
    readonly_fields = ("eve_type", "output_type", "daily_quantity")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(EveCharacterPlanet)
class EveCharacterPlanetAdmin(admin.ModelAdmin):
    list_display = (
        "character",
        "planet_id",
        "planet_type",
        "solar_system_id",
        "upgrade_level",
        "num_pins",
        "last_update",
    )
    list_filter = ("planet_type", "upgrade_level")
    search_fields = (
        "character__character_name",
        "planet_id",
        "solar_system_id",
    )
    autocomplete_fields = ("character",)
    readonly_fields = ("last_update",)
    inlines = [EveCharacterPlanetOutputInline]


@admin.register(EveCharacterPlanetOutput)
class EveCharacterPlanetOutputAdmin(admin.ModelAdmin):
    list_display = (
        "planet",
        "eve_type",
        "output_type",
        "daily_quantity",
    )
    list_filter = ("output_type",)
    search_fields = (
        "planet__character__character_name",
        "eve_type__name",
    )


@admin.register(EveUniverseSchematic)
class EveUniverseSchematicAdmin(admin.ModelAdmin):
    list_display = ("schematic_id", "schematic_name", "cycle_time")
    search_fields = ("schematic_name",)
    ordering = ("schematic_id",)


# ---------------------------------------------------------------------------
# Corporations
# ---------------------------------------------------------------------------


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
        corp = EveCorporation.objects.get(pk=object_id)
        update_corporation.delay(corp.corporation_id)
        self.message_user(
            request,
            f"Refresh queued for corporation \u201c{corp.name}\u201d.",
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


@admin.register(EveCorporationContract)
class EveCorporationContractAdmin(admin.ModelAdmin):
    list_display = (
        "contract_id",
        "corporation",
        "type",
        "status",
        "price",
        "date_issued",
        "date_expired",
    )
    list_filter = ("type", "status")
    search_fields = ("contract_id", "corporation__name")
    readonly_fields = ("updated_at",)
    autocomplete_fields = ("corporation",)
    date_hierarchy = "date_issued"


@admin.register(EveCorporationIndustryJob)
class EveCorporationIndustryJobAdmin(admin.ModelAdmin):
    list_display = (
        "job_id",
        "corporation",
        "activity_id",
        "blueprint_type_id",
        "status",
        "runs",
        "start_date",
        "end_date",
        "updated_at",
    )
    list_filter = ("status", "activity_id", "corporation")
    search_fields = ("job_id", "corporation__name")
    readonly_fields = ("updated_at",)
    autocomplete_fields = ("corporation",)


@admin.register(EveCorporationBlueprint)
class EveCorporationBlueprintAdmin(admin.ModelAdmin):
    list_display = (
        "item_id",
        "corporation",
        "type_id",
        "location_id",
        "location_flag",
        "material_efficiency",
        "time_efficiency",
        "quantity",
        "runs",
        "updated_at",
    )
    list_filter = ("corporation", "location_flag")
    search_fields = ("corporation__name", "item_id", "type_id")
    readonly_fields = ("updated_at",)
    autocomplete_fields = ("corporation",)


# ---------------------------------------------------------------------------
# Alliances
# ---------------------------------------------------------------------------


@admin.register(EveAlliance)
class EveAllianceAdmin(admin.ModelAdmin):
    list_display = ("name", "alliance_id")
    search_fields = ("name",)


@admin.register(EveLocation)
class EveLocationAdmin(admin.ModelAdmin):
    list_display = (
        "location_id",
        "location_name",
        "solar_system_name",
        "market_active",
        "prices_active",
        "freight_active",
        "staging_active",
    )
    search_fields = ("location_name", "short_name", "solar_system_name")
    list_filter = (
        "market_active",
        "prices_active",
        "freight_active",
        "staging_active",
    )
    ordering = ("location_name",)


# ---------------------------------------------------------------------------
# Admin index grouping
#
# Split the single "eveonline" app section on the admin index page into three
# logical groups: Characters, Corporations, and Alliances.
# ---------------------------------------------------------------------------

_CHARACTER_MODELS = {
    "evecharacter",
    "eveplayer",
    "evecharacterasset",
    "evecharacterskill",
    "evecharactercontract",
    "evecharacterindustryjob",
    "evecharacterminingentry",
    "evecharacterplanet",
    "evecharacterplanetoutput",
    "evetag",
    "evecharactertag",
    "eveskillset",
}

_CORPORATION_MODELS = {
    "evecorporation",
    "evecorporationcontract",
    "evecorporationindustryjob",
}

_ALLIANCE_MODELS = {
    "evealliance",
    "evelocation",
}

_GROUPS = [
    ("Characters", _CHARACTER_MODELS),
    ("Corporations", _CORPORATION_MODELS),
    ("Alliances & Locations", _ALLIANCE_MODELS),
]

_original_get_app_list = admin.AdminSite.get_app_list


def _grouped_get_app_list(self, request, app_label=None):
    app_list = _original_get_app_list(self, request, app_label)
    result = []
    for app in app_list:
        if app["app_label"] != "eveonline":
            result.append(app)
            continue
        all_models = app["models"]
        for group_name, model_names in _GROUPS:
            group_models = [
                m
                for m in all_models
                if m["object_name"].lower() in model_names
            ]
            if group_models:
                result.append(
                    {**app, "name": group_name, "models": group_models}
                )
    return result


admin.AdminSite.get_app_list = _grouped_get_app_list
