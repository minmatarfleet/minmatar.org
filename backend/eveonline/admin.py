from django.contrib import admin
from django.contrib import messages
from django import forms
from django.db.models import F, Q
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter

from fittings.models import FittingTag

from esi.models import CallbackRedirect, Scope, Token

from .models import (
    EvePlayer,
    EveAlliance,
    EveCharacter,
    EveCharacterBlueprint,
    EveCharacterClone,
    EveCharacterContract,
    EveCharacterIndustryJob,
    EveCharacterPlanet,
    EveCharacterPlanetOutput,
    EveCorporation,
    EveCorporationBlueprint,
    EveCorporationContract,
    EveCorporationIndustryJob,
    EveCorporationWalletJournalEntry,
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


class EveCharacterTagInline(admin.TabularInline):
    model = EveCharacterTag
    extra = 1
    autocomplete_fields = ("tag",)


def _format_corp_label(name, ticker, corp_id):
    if name and ticker:
        return f"{name} ({ticker})"
    if name:
        return name
    return str(corp_id)


MINMATAR_FLEET_ALLIANCE_ID = 99011978


def _minmatar_fleet_corporations():
    return EveCorporation.objects.filter(
        alliance__alliance_id=MINMATAR_FLEET_ALLIANCE_ID
    )


class EveCharacterCorporationFilter(admin.SimpleListFilter):
    title = "corporation"
    parameter_name = "corporation"

    def lookups(self, request, model_admin):
        corp_ids = (
            EveCharacter.objects.exclude(corporation_id__isnull=True)
            .values_list("corporation_id", flat=True)
            .distinct()
        )
        corps = (
            _minmatar_fleet_corporations()
            .filter(corporation_id__in=corp_ids)
            .order_by("name")
            .values_list("corporation_id", "name", "ticker")
        )
        return [
            (corp_id, _format_corp_label(name, ticker, corp_id))
            for corp_id, name, ticker in corps
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(corporation_id=self.value())
        return queryset


class EveCharacterAllianceFilter(admin.SimpleListFilter):
    title = "alliance"
    parameter_name = "alliance"

    def lookups(self, request, model_admin):
        alliance_ids = (
            EveCharacter.objects.exclude(alliance_id__isnull=True)
            .filter(alliance_id=MINMATAR_FLEET_ALLIANCE_ID)
            .values_list("alliance_id", flat=True)
            .distinct()
        )
        alliances = (
            EveAlliance.objects.filter(alliance_id__in=alliance_ids)
            .order_by("name")
            .values_list("alliance_id", "name", "ticker")
        )
        return [
            (
                alliance_id,
                _format_corp_label(name, ticker, alliance_id),
            )
            for alliance_id, name, ticker in alliances
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(alliance_id=self.value())
        return queryset


class EveCharacterPrimaryFilter(admin.SimpleListFilter):
    title = "primary character"
    parameter_name = "is_primary"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                user__eveplayer__primary_character_id=F("pk")
            )
        if self.value() == "no":
            return queryset.exclude(
                user__eveplayer__primary_character_id=F("pk")
            )
        return queryset


class EveCharacterDiscordFilter(admin.SimpleListFilter):
    title = "discord"
    parameter_name = "discord"

    def lookups(self, request, model_admin):
        return (
            ("linked", "Linked"),
            ("not_linked", "Not linked"),
        )

    def queryset(self, request, queryset):
        if self.value() == "linked":
            return queryset.filter(user__discord_user__isnull=False)
        if self.value() == "not_linked":
            return queryset.filter(
                Q(user__isnull=True) | Q(user__discord_user__isnull=True)
            )
        return queryset


@admin.register(EveCharacter)
class EveCharacterAdmin(admin.ModelAdmin):
    list_display = (
        "character_name",
        "corporation_display",
        "alliance_display",
        "primary_eve_character",
        "user",
    )
    search_fields = (
        "character_name",
        "=character_id",
        "user__username",
        "user__eveplayer__primary_character__character_name",
        "user__discord_user__discord_tag",
        "user__discord_user__nickname",
    )
    list_filter = (
        EveCharacterCorporationFilter,
        EveCharacterAllianceFilter,
        EveCharacterPrimaryFilter,
        EveCharacterDiscordFilter,
    )
    list_per_page = 50
    inlines = [EveCharacterTagInline]

    @admin.display(description="Corporation")
    def corporation_display(self, obj):
        if not obj.corporation_id:
            return "-"
        corp = EveCorporation.objects.filter(
            corporation_id=obj.corporation_id
        ).first()
        if not corp:
            return obj.corporation_id
        return _format_corp_label(corp.name, corp.ticker, obj.corporation_id)

    @admin.display(description="Alliance")
    def alliance_display(self, obj):
        if not obj.alliance_id:
            return "-"
        alliance = EveAlliance.objects.filter(
            alliance_id=obj.alliance_id
        ).first()
        if not alliance:
            return obj.alliance_id
        return _format_corp_label(
            alliance.name, alliance.ticker, obj.alliance_id
        )

    @admin.display(description="Primary character")
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


@admin.register(EveTag)
class EveTagAdmin(admin.ModelAdmin):
    list_display = ("title", "description")
    search_fields = ("title", "description")


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


class EveCharacterCloneInline(admin.TabularInline):
    model = EveCharacterClone
    extra = 0
    readonly_fields = (
        "clone_id",
        "name",
        "location_id",
        "location_name",
        "implants",
        "total_value_isk",
        "is_active",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(EveCharacterClone)
class EveCharacterCloneAdmin(admin.ModelAdmin):
    list_display = (
        "character",
        "name",
        "clone_id",
        "location_name",
        "total_value_isk",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("character__character_name", "name", "location_name")
    autocomplete_fields = ("character",)
    readonly_fields = ("implants", "total_value_isk")


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


@admin.register(EveCorporationWalletJournalEntry)
class EveCorporationWalletJournalEntryAdmin(admin.ModelAdmin):
    list_display = (
        "ref_id",
        "corporation",
        "division",
        "date",
        "ref_type",
        "amount",
        "balance",
        "first_party_id",
        "second_party_id",
    )
    list_filter = ("ref_type", "corporation", "division")
    search_fields = ("ref_id", "corporation__name", "description")
    readonly_fields = ("updated_at",)
    autocomplete_fields = ("corporation",)
    date_hierarchy = "date"


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


@admin.register(EveSkillset)
class EveSkillsetAdmin(admin.ModelAdmin):
    list_display = ("name", "total_skill_points")


@admin.register(EveLocation)
class EveLocationAdmin(SafeDeleteAdmin):
    field_to_highlight = "location_name"

    class EveLocationAdminForm(forms.ModelForm):
        market_categories = forms.MultipleChoiceField(
            choices=FittingTag.choices,
            required=False,
            widget=forms.CheckboxSelectMultiple,
            label="Market order categories",
            help_text="Fittings sharing ANY of these tags qualify for sell orders.",
        )

        class Meta:
            model = EveLocation
            fields = "__all__"

    form = EveLocationAdminForm

    list_display = (
        "highlight_deleted_field",
        "location_id",
        "solar_system_name",
        "is_structure",
        "market_active",
        "prices_active",
        "price_baseline",
        "freight_active",
        "staging_active",
        "deleted",
    )
    search_fields = ("location_name", "short_name", "solar_system_name")
    list_filter = (
        SafeDeleteAdminFilter,
        "is_structure",
        "market_active",
        "prices_active",
        "price_baseline",
        "freight_active",
        "staging_active",
    )
    ordering = ("location_name",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "location_id",
                    "location_name",
                    "short_name",
                    "solar_system_id",
                    "solar_system_name",
                    "region_id",
                    "is_structure",
                )
            },
        ),
        (
            "Market",
            {
                "fields": (
                    "market_active",
                    "prices_active",
                    "price_baseline",
                    "market_categories",
                )
            },
        ),
        (
            "Other",
            {
                "fields": (
                    "freight_active",
                    "staging_active",
                )
            },
        ),
    )


EveLocationAdmin.highlight_deleted_field.short_description = "Location name"


# ---------------------------------------------------------------------------
# Admin index grouping
#
# Split the single "eveonline" app section on the admin index page into logical
# groups. Other apps are folded in: applications → Corporations,
# access_lists/sovereignty/structures/srp → Alliance, community-related apps →
# Community, fittings → Readiness, industry/freight → Supply, market/evelocation →
# Staging Systems (first on the index), auth/django_celery_beat → System (last).
# ---------------------------------------------------------------------------

_CHARACTER_MODELS = {
    "evecharacter",
    "eveplayer",
    "evecharacterasset",
    "evecharacterskill",
    "evecharactercontract",
    "evecharacterindustryjob",
    "evecharacterclone",
    "evecharacterplanet",
}

_SYSTEM_EVEONLINE_MODELS = {
    "evetag",
}

_CORPORATION_MODELS = {
    "evecorporation",
    "evecorporationapplication",
    "evecorporationcontract",
    "evecorporationindustryjob",
}

_ALLIANCE_MODELS = {
    "evealliance",
    "eveskillset",
    "eveaccesslist",
    "eveaccesslistmember",
}

_STAGING_SYSTEMS_APPS = {"market"}

_STAGING_SYSTEMS_EVEONLINE_MODELS = {
    "evelocation",
}

_ALLIANCE_EXTRA_APPS = {"access_lists", "sovereignty", "structures", "srp"}

_COMMUNITY_APPS = {
    "audit",
    "discord",
    "groups",
    "help_tickets",
    "mumble",
    "onboarding",
    "posts",
    "reddit",
    "referrals",
}

_SYSTEM_APPS = {"auth", "django_celery_beat", "subscriptions"}

_READINESS_APPS = {"fittings"}

_SUPPLY_APPS = {"industry", "freight"}

_ABSORBED_APPS = (
    _COMMUNITY_APPS
    | _SYSTEM_APPS
    | _READINESS_APPS
    | _STAGING_SYSTEMS_APPS
    | _SUPPLY_APPS
    | _ALLIANCE_EXTRA_APPS
    | {"applications"}
)

_SYNTHETIC_APP_GROUPS = {
    "Community": ("groups", _COMMUNITY_APPS),
    "Readiness": ("fittings", _READINESS_APPS),
    "Supply": ("industry", _SUPPLY_APPS),
}

_GROUPS = [
    ("Characters", _CHARACTER_MODELS),
    ("Corporations", _CORPORATION_MODELS),
    ("Alliance", _ALLIANCE_MODELS),
    ("Community", None),
    ("Readiness", None),
    ("Supply", None),
]

_original_get_app_list = admin.AdminSite.get_app_list


def _grouped_get_app_list(self, request, app_label=None):  # noqa: C901
    app_list = _original_get_app_list(self, request, app_label)
    absorbed = {}
    eveonline_app = None
    other_apps = []
    for app in app_list:
        label = app["app_label"]
        if label == "eveonline":
            eveonline_app = app
        elif label in _ABSORBED_APPS:
            absorbed[label] = app
        else:
            other_apps.append(app)

    result = list(other_apps)
    if not eveonline_app:
        return result

    all_eveonline_models = eveonline_app["models"]
    grouped_sections = []
    for group_name, model_names in _GROUPS:
        if model_names is None:
            base_label, app_labels = _SYNTHETIC_APP_GROUPS[group_name]
            group_models = []
            for group_app_label in sorted(app_labels):
                group_models.extend(
                    absorbed.get(group_app_label, {}).get("models", [])
                )
            base_app = absorbed.get(base_label) or eveonline_app
        else:
            group_models = [
                m
                for m in all_eveonline_models
                if m["object_name"].lower() in model_names
            ]
            base_app = eveonline_app
            if group_name == "Corporations":
                group_models.extend(
                    m
                    for m in absorbed.get("applications", {}).get("models", [])
                    if m["object_name"].lower() in model_names
                )
            elif group_name == "Alliance":
                for extra_app_label in sorted(_ALLIANCE_EXTRA_APPS):
                    group_models.extend(
                        absorbed.get(extra_app_label, {}).get("models", [])
                    )

        if group_models:
            grouped_sections.append(
                {**base_app, "name": group_name, "models": group_models}
            )

    staging_models = [
        m
        for m in all_eveonline_models
        if m["object_name"].lower() in _STAGING_SYSTEMS_EVEONLINE_MODELS
    ]
    for staging_app_label in sorted(_STAGING_SYSTEMS_APPS):
        staging_models.extend(
            absorbed.get(staging_app_label, {}).get("models", [])
        )

    system_models = []
    for system_app_label in sorted(_SYSTEM_APPS):
        system_models.extend(
            absorbed.get(system_app_label, {}).get("models", [])
        )
    system_models.extend(
        m
        for m in all_eveonline_models
        if m["object_name"].lower() in _SYSTEM_EVEONLINE_MODELS
    )

    final = list(result)
    final.extend(grouped_sections)
    if system_models:
        final.append(
            {
                **(absorbed.get("auth") or eveonline_app),
                "name": "System",
                "models": system_models,
            }
        )
    if staging_models:
        final.insert(
            0,
            {
                **(absorbed.get("market") or eveonline_app),
                "name": "Staging Systems",
                "models": staging_models,
            },
        )
    return final


admin.AdminSite.get_app_list = _grouped_get_app_list
