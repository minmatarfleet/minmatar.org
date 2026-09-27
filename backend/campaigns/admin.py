"""Django admin for live campaigns.

Operators configure theaters, structures, parties, week targets and the
rest from here; the frontend cog opens the campaign change page.

The campaign change form uses django-admin-tabs so operators work through
focused tabs (story, theaters, structures) instead of one long page.
"""

from django.contrib import admin, messages
from django.utils import timezone
from django_admin_tabs import AdminChangeListTab, AdminTab, TabbedModelAdmin

from campaigns.forms import (
    PRIORITY_TO_ROLE,
    CampaignConstellationTheaterForm,
    CampaignRegionTheaterForm,
    CampaignSystemTheaterForm,
    cover_image_formfield,
)
from campaigns.services import plan
from campaigns.services import structures as structure_service
from campaigns.models import (
    AreaScope,
    Campaign,
    CampaignAdvantageReading,
    CampaignAdvantageState,
    CampaignArea,
    CampaignAward,
    CampaignComplexCompletion,
    CampaignDailyOrder,
    CampaignEnlistment,
    CampaignEnlistmentCharacter,
    CampaignEnlistmentPeriod,
    CampaignEvent,
    CampaignFitting,
    CampaignKillmail,
    CampaignKillmailParticipant,
    CampaignParty,
    CampaignOrderProgress,
    CampaignParticipantDay,
    CampaignParticipantStat,
    CampaignSiteCompletion,
    CampaignStructure,
    CampaignSystem,
    CampaignSystemArc,
    CampaignSystemInsurgency,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
    SystemRole,
)
from eveuniverse.models import EveConstellation, EveRegion, EveSolarSystem

# --- Map lookups (autocomplete; extend eveuniverse registration) ------------


def _ensure_map_autocomplete(model, search):
    """Unregister stock eveuniverse admin and re-register with search_fields."""
    if admin.site.is_registered(model):
        admin.site.unregister(model)

    class MapEntityAdmin(admin.ModelAdmin):
        list_display = ("name", "id")

        def has_module_permission(self, request):
            return False

    MapEntityAdmin.search_fields = search
    admin.site.register(model, MapEntityAdmin)


_ensure_map_autocomplete(EveSolarSystem, ("name", "=id"))
_ensure_map_autocomplete(EveConstellation, ("name", "=id"))
_ensure_map_autocomplete(EveRegion, ("name", "=id"))


# --- Inlines (theater tab) --------------------------------------------------


class CampaignSystemInline(admin.TabularInline):
    model = CampaignSystem
    form = CampaignSystemTheaterForm
    extra = 1
    show_change_link = True
    autocomplete_fields = ("eve_solar_system",)
    fields = (
        "eve_solar_system",
        "priority",
        "goal",
        "is_fw_objective",
        "retired_at",
    )
    verbose_name = "System"
    verbose_name_plural = "Systems"


class CampaignConstellationInline(admin.TabularInline):
    model = CampaignArea
    form = CampaignConstellationTheaterForm
    extra = 1
    show_change_link = True
    autocomplete_fields = ("eve_constellation",)
    fields = ("eve_constellation", "goal", "priority")
    verbose_name = "Constellation"
    verbose_name_plural = "Constellations"

    def get_queryset(self, request):
        return (
            super().get_queryset(request).filter(scope=AreaScope.CONSTELLATION)
        )


class CampaignRegionInline(admin.TabularInline):
    model = CampaignArea
    form = CampaignRegionTheaterForm
    extra = 1
    show_change_link = True
    autocomplete_fields = ("eve_region",)
    fields = ("eve_region", "goal", "priority")
    verbose_name = "Region"
    verbose_name_plural = "Regions"

    def get_queryset(self, request):
        return super().get_queryset(request).filter(scope=AreaScope.REGION)


# --- Campaign change tabs ---------------------------------------------------


class CampaignOverviewTab(AdminTab, admin.ModelAdmin):
    """Read-only pulse of the campaign — edit on Story / Theater / Settings."""

    admin_tab_name = "Overview"
    readonly_fields = (
        "name",
        "kind",
        "status",
        "visibility",
        "short_code",
        "start_at",
        "end_at",
        "created_by",
        "created_at",
        "updated_at",
        "overview_system_count",
        "overview_area_count",
        "overview_structure_count",
        "overview_party_count",
        "overview_enlistment_count",
        "overview_commander_order",
    )
    fieldsets = (
        (
            "At a glance",
            {
                "fields": (
                    "name",
                    "kind",
                    "status",
                    "visibility",
                    "short_code",
                ),
                "description": (
                    "Read-only summary. Edit the title and story on Story, "
                    "theaters on Theater, and status or Discord on Settings."
                ),
            },
        ),
        (
            "Schedule",
            {
                "fields": ("start_at", "end_at"),
            },
        ),
        (
            "Pulse",
            {
                "fields": (
                    "overview_system_count",
                    "overview_area_count",
                    "overview_structure_count",
                    "overview_party_count",
                    "overview_enlistment_count",
                    "overview_commander_order",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at", "created_by"),
            },
        ),
    )

    @admin.display(description="Systems")
    def overview_system_count(self, obj: Campaign) -> int:
        if obj is None or not obj.pk:
            return 0
        return obj.systems.filter(retired_at__isnull=True).count()

    @admin.display(description="Constellations / regions")
    def overview_area_count(self, obj: Campaign) -> int:
        if obj is None or not obj.pk:
            return 0
        return obj.areas.count()

    @admin.display(description="Structures")
    def overview_structure_count(self, obj: Campaign) -> int:
        if obj is None or not obj.pk:
            return 0
        return obj.structures.count()

    @admin.display(description="Parties")
    def overview_party_count(self, obj: Campaign) -> int:
        if obj is None or not obj.pk:
            return 0
        return obj.parties.count()

    @admin.display(description="Enlisted pilots")
    def overview_enlistment_count(self, obj: Campaign) -> int:
        if obj is None or not obj.pk:
            return 0
        return obj.enlistments.count()

    @admin.display(description="Commander's order")
    def overview_commander_order(self, obj: Campaign) -> str:
        if obj is None:
            return "—"
        text = (obj.commander_order_text or "").strip()
        if not text:
            return "Not set"
        status = "draft" if obj.commander_order_is_draft else "published"
        preview = text if len(text) <= 80 else f"{text[:77]}…"
        return f"{status}: {preview}"

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context.update(
            {
                "show_save": False,
                "show_save_and_continue": False,
                "show_save_and_add_another": False,
            }
        )
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )


class CampaignStoryTab(AdminTab, admin.ModelAdmin):
    admin_tab_name = "Story"
    fieldsets = (
        (
            "Member-facing story",
            {
                "fields": (
                    "name",
                    "tagline",
                    "description_md",
                    "cover_image_url",
                ),
                "description": (
                    "Title and tagline show on the campaign list and detail "
                    "header. Description is the longer story under them; "
                    "cover is the hero art from the site gallery."
                ),
            },
        ),
        (
            "Commander's order",
            {
                "fields": (
                    "commander_order_text",
                    "commander_order_is_draft",
                    "commander_order_set_at",
                ),
                "description": (
                    "Shown above this week's objectives on the campaign "
                    "page. Leave as draft until you are ready to publish, or "
                    "use the list actions to auto-draft from the week plan."
                ),
            },
        ),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "cover_image_url":
            current = ""
            object_id = (request.resolver_match.kwargs or {}).get("object_id")
            if object_id:
                current = (
                    Campaign.objects.filter(pk=object_id)
                    .values_list("cover_image_url", flat=True)
                    .first()
                    or ""
                )
            return cover_image_formfield(current_value=current)
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "name" and formfield is not None:
            formfield.label = "Title"
        return formfield


class CampaignTheatersTab(AdminTab, admin.ModelAdmin):
    """Systems, constellations, and regions for this campaign."""

    admin_tab_name = "Theater"
    inlines = [
        CampaignSystemInline,
        CampaignConstellationInline,
        CampaignRegionInline,
    ]
    fieldsets = (
        (
            None,
            {
                "fields": (),
                "description": (
                    "Add theaters in three sections. Use the type-ahead to "
                    "pick a system, constellation, or region by name. Set a "
                    "goal on each so members know the focus."
                ),
            },
        ),
    )


class CampaignPartiesTab(AdminChangeListTab, admin.ModelAdmin):
    admin_tab_name = "Parties"
    model = CampaignParty
    parent_model = Campaign
    fk_field = "campaign"
    list_display = (
        "name",
        "ticker",
        "kind",
        "side",
        "character_id",
        "corporation_id",
        "alliance_id",
        "faction_id",
    )
    list_filter = ("kind", "side")
    list_editable = ("kind", "side")
    search_fields = ("name", "ticker", "alliance_id", "corporation_id")
    fields = (
        "name",
        "ticker",
        "kind",
        "side",
        "character_id",
        "corporation_id",
        "alliance_id",
        "faction_id",
    )


class CampaignStructuresTab(AdminChangeListTab, admin.ModelAdmin):
    admin_tab_name = "Structures"
    model = CampaignStructure
    parent_model = Campaign
    fk_field = "campaign"
    list_display = (
        "name",
        "structure_type",
        "system_name",
        "corporation_name",
        "related_alliance_name",
        "structure_affiliation",
        "status",
        "reinforce_hour",
    )
    list_filter = ("status", "structure_type", "source")
    list_editable = ("status", "reinforce_hour")
    search_fields = (
        "name",
        "system_name",
        "corporation_name",
        "alliance_name",
        "related_alliance_name",
    )
    raw_id_fields = ("timer", "killmail", "created_by")
    readonly_fields = ("created_at", "updated_at", "structure_affiliation")
    fields = (
        "name",
        "structure_type",
        "type_id",
        "status",
        "source",
        "structure_affiliation",
        "system_name",
        "solar_system_id",
        "eve_structure_id",
        "corporation_id",
        "corporation_name",
        "alliance_id",
        "alliance_name",
        "related_alliance_id",
        "related_alliance_name",
        "fitting",
        "reinforce_hour",
        "timer",
        "destroyed_at",
        "killmail",
        "created_by",
    )

    @admin.display(description="Affiliation")
    def structure_affiliation(self, obj: CampaignStructure) -> str:
        if obj is None or not obj.pk:
            return "—"
        return structure_service.structure_affiliation(obj)


class CampaignSettingsTab(AdminTab, admin.ModelAdmin):
    admin_tab_name = "Settings"
    raw_id_fields = ("created_by", "default_fleet_audience")
    fieldsets = (
        (
            "Identity",
            {
                "fields": ("slug", "short_code", "kind"),
                "description": (
                    "URL slug, donation short code, and display kind. "
                    "Title and cover live on the Story tab."
                ),
            },
        ),
        (
            "Lifecycle",
            {
                "fields": (
                    "status",
                    "visibility",
                    "start_at",
                    "end_at",
                    "created_by",
                ),
            },
        ),
        (
            "Discord and fleets",
            {
                "fields": (
                    "discord_channel_id",
                    "voice_channel_ids",
                    "default_fleet_audience",
                ),
            },
        ),
        (
            "Scoring and orders",
            {
                "fields": ("scoring", "order_pool"),
                "description": (
                    "JSON overrides for scoring weights and the daily order "
                    "point pool. Leave empty to use defaults."
                ),
            },
        ),
        (
            "Donations",
            {
                "fields": ("donation_corporation_id", "donation_division"),
            },
        ),
    )


# --- Campaign ---------------------------------------------------------------


@admin.register(Campaign)
class CampaignAdmin(TabbedModelAdmin, admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "short_code",
        "kind",
        "status",
        "visibility",
        "start_at",
        "end_at",
        "system_count",
        "structure_count",
    )
    list_filter = ("kind", "status", "visibility")
    search_fields = ("name", "slug", "short_code", "tagline")
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ("created_by", "default_fleet_audience")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "start_at"
    actions = (
        "propose_week_targets",
        "draft_commander_orders",
        "publish_commander_orders",
    )
    # Add form only — change redirects into tabs.
    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "name",
                    "slug",
                    "short_code",
                    "kind",
                    "tagline",
                    "description_md",
                    "cover_image_url",
                ),
            },
        ),
        (
            "Lifecycle",
            {
                "fields": (
                    "status",
                    "visibility",
                    "start_at",
                    "end_at",
                    "created_by",
                ),
            },
        ),
    )
    admin_tabs = [
        CampaignOverviewTab,
        CampaignStoryTab,
        CampaignTheatersTab,
        CampaignPartiesTab,
        CampaignStructuresTab,
        CampaignSettingsTab,
    ]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "cover_image_url":
            return cover_image_formfield()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description="Systems")
    def system_count(self, obj: Campaign) -> int:
        return obj.systems.filter(retired_at__isnull=True).count()

    @admin.display(description="Structures")
    def structure_count(self, obj: Campaign) -> int:
        return obj.structures.count()

    @admin.action(description="Propose week targets from arcs")
    def propose_week_targets(self, request, queryset):
        proposed = 0
        for campaign in queryset:
            proposed += plan.propose_week(campaign)
        self.message_user(
            request,
            f"Proposed {proposed} week target(s) across {queryset.count()} "
            f"campaign(s).",
            messages.SUCCESS,
        )

    @admin.action(description="Draft commander's order from week plan")
    def draft_commander_orders(self, request, queryset):
        updated = 0
        for campaign in queryset:
            campaign.commander_order_text = plan.draft_commander_order(
                campaign
            )
            campaign.commander_order_set_at = timezone.now()
            campaign.commander_order_is_draft = True
            campaign.save(
                update_fields=[
                    "commander_order_text",
                    "commander_order_set_at",
                    "commander_order_is_draft",
                ]
            )
            updated += 1
        self.message_user(
            request,
            f"Drafted commander's order for {updated} campaign(s).",
            messages.SUCCESS,
        )

    @admin.action(description="Publish commander's order (clear draft)")
    def publish_commander_orders(self, request, queryset):
        ready = queryset.exclude(commander_order_text="")
        count = ready.update(
            commander_order_is_draft=False,
            commander_order_set_at=timezone.now(),
        )
        skipped = queryset.count() - count
        message = f"Published commander's order for {count} campaign(s)."
        if skipped:
            message += f" Skipped {skipped} with empty order text."
        self.message_user(request, message, messages.SUCCESS)


# --- Theaters ---------------------------------------------------------------


class CampaignSystemArcInline(admin.StackedInline):
    model = CampaignSystemArc
    extra = 0
    max_num = 1
    can_delete = True


class CampaignWeekTargetInline(admin.TabularInline):
    model = CampaignWeekTarget
    extra = 0
    show_change_link = True
    fields = (
        "week_start",
        "metric",
        "target",
        "progress",
        "pace_expected",
        "proposed",
        "baseline",
    )
    readonly_fields = ("progress", "pace_expected", "baseline")


@admin.register(CampaignSystem)
class CampaignSystemAdmin(admin.ModelAdmin):
    form = CampaignSystemTheaterForm
    list_display = (
        "name",
        "campaign",
        "solar_system_id",
        "priority",
        "goal",
        "is_fw_objective",
        "retired_at",
    )
    list_filter = (
        "campaign",
        "priority",
        "goal",
        "is_fw_objective",
    )
    list_editable = ("priority", "goal", "is_fw_objective")
    search_fields = ("name", "solar_system_id", "campaign__slug")
    raw_id_fields = ("campaign",)
    autocomplete_fields = ("eve_solar_system",)
    inlines = [CampaignSystemArcInline, CampaignWeekTargetInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "campaign",
                    "eve_solar_system",
                    "name",
                    "solar_system_id",
                    "region_id",
                ),
            },
        ),
        (
            "Theater focus",
            {
                "fields": (
                    "is_fw_objective",
                    "goal",
                    "priority",
                    "added_at",
                    "retired_at",
                ),
                "description": (
                    "FW objectives drive plex/VP/advantage and kill scoring. "
                    "Ops theaters (is_fw_objective off) are for structure "
                    "hunting and member guidance only. Priority orders the "
                    "member boards (high first)."
                ),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        obj.sync_from_eve_solar_system()
        obj.role = PRIORITY_TO_ROLE.get(obj.priority, SystemRole.SECONDARY)
        super().save_model(request, obj, form, change)


@admin.register(CampaignArea)
class CampaignAreaAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "scope",
        "campaign",
        "goal",
        "priority",
        "constellation_id",
        "region_id",
    )
    list_filter = ("campaign", "scope", "goal", "priority")
    list_editable = ("goal", "priority")
    search_fields = ("name", "campaign__slug")
    raw_id_fields = ("campaign",)
    autocomplete_fields = ("eve_constellation", "eve_region")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "campaign",
                    "scope",
                    "eve_constellation",
                    "eve_region",
                    "name",
                    "constellation_id",
                    "region_id",
                    "goal",
                    "priority",
                ),
                "description": (
                    "Constellation or region ops theater. Prefer the "
                    "type-ahead fields; ids and name fill in automatically."
                ),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        obj.sync_from_eve_lookups()
        super().save_model(request, obj, form, change)


@admin.register(CampaignSystemArc)
class CampaignSystemArcAdmin(admin.ModelAdmin):
    list_display = (
        "campaign_system",
        "target_state",
        "due_at",
        "advantage_task",
        "advantage_target",
        "contest_ceiling",
    )
    list_filter = ("target_state", "advantage_task")
    search_fields = (
        "campaign_system__name",
        "campaign_system__campaign__slug",
    )
    raw_id_fields = ("campaign_system",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "campaign_system",
                    "target_state",
                    "due_at",
                    "vp_needed_at_start",
                ),
            },
        ),
        (
            "Defend / contest",
            {
                "fields": ("contest_ceiling", "advantage_floor"),
            },
        ),
        (
            "Advantage task",
            {
                "fields": ("advantage_task", "advantage_target"),
            },
        ),
    )


@admin.register(CampaignSystemInsurgency)
class CampaignSystemInsurgencyAdmin(admin.ModelAdmin):
    list_display = (
        "campaign_system",
        "suppression_stage",
        "corruption_stage",
        "valid_from",
        "valid_until",
        "source",
    )
    list_filter = ("source",)
    raw_id_fields = ("campaign_system",)


# --- Structures and parties -------------------------------------------------


@admin.register(CampaignParty)
class CampaignPartyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "ticker",
        "kind",
        "side",
        "campaign",
        "character_id",
        "corporation_id",
        "alliance_id",
        "faction_id",
    )
    list_filter = ("campaign", "kind", "side")
    list_editable = ("kind", "side")
    search_fields = ("name", "ticker", "alliance_id", "corporation_id")
    raw_id_fields = ("campaign",)


@admin.register(CampaignStructure)
class CampaignStructureAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "structure_type",
        "system_name",
        "corporation_name",
        "related_alliance_name",
        "structure_affiliation",
        "status",
        "reinforce_hour",
        "campaign",
    )
    list_filter = ("campaign", "status", "structure_type", "source")
    list_editable = ("status", "reinforce_hour")
    search_fields = (
        "name",
        "system_name",
        "corporation_name",
        "alliance_name",
        "related_alliance_name",
    )
    raw_id_fields = ("campaign", "timer", "killmail", "created_by")
    readonly_fields = ("created_at", "updated_at", "structure_affiliation")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "campaign",
                    "name",
                    "structure_type",
                    "type_id",
                    "status",
                    "source",
                    "structure_affiliation",
                ),
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "system_name",
                    "solar_system_id",
                    "eve_structure_id",
                ),
            },
        ),
        (
            "Ownership",
            {
                "fields": (
                    "corporation_id",
                    "corporation_name",
                    "alliance_id",
                    "alliance_name",
                    "related_alliance_id",
                    "related_alliance_name",
                ),
                "description": (
                    "Affiliation (hostile / friendly / neutral) is derived "
                    "from campaign parties matching owner or affiliated "
                    "alliance."
                ),
            },
        ),
        (
            "Recon",
            {
                "fields": ("fitting", "reinforce_hour", "timer"),
            },
        ),
        (
            "Destruction",
            {
                "classes": ("collapse",),
                "fields": ("destroyed_at", "killmail"),
            },
        ),
        (
            "Meta",
            {
                "classes": ("collapse",),
                "fields": ("created_by", "created_at", "updated_at"),
            },
        ),
    )

    @admin.display(description="Affiliation")
    def structure_affiliation(self, obj: CampaignStructure) -> str:
        if obj is None or not obj.pk:
            return "—"
        return structure_service.structure_affiliation(obj)


@admin.register(CampaignFitting)
class CampaignFittingAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "fitting",
        "role_label",
        "srp_eligible",
        "order",
    )
    list_filter = ("campaign", "srp_eligible")
    list_editable = ("role_label", "srp_eligible", "order")
    raw_id_fields = ("campaign", "fitting")


# --- Plan / week ------------------------------------------------------------


@admin.register(CampaignWeekTarget)
class CampaignWeekTargetAdmin(admin.ModelAdmin):
    list_display = (
        "campaign_system",
        "week_start",
        "metric",
        "target",
        "progress",
        "pace_expected",
        "proposed",
        "accepted_by",
    )
    list_filter = ("week_start", "metric", "proposed")
    list_editable = ("target", "proposed")
    search_fields = (
        "campaign_system__name",
        "campaign_system__campaign__slug",
    )
    raw_id_fields = ("campaign_system", "accepted_by")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "campaign_system",
                    "week_start",
                    "metric",
                    "target",
                    "proposed",
                    "accepted_by",
                    "accepted_at",
                ),
            },
        ),
        (
            "Progress",
            {
                "fields": (
                    "progress",
                    "pace_expected",
                    "baseline",
                    "days_under_line",
                    "last_week_actual",
                    "projected_arc_date",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(CampaignDailyOrder)
class CampaignDailyOrderAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "day",
        "kind",
        "campaign_system",
        "points",
        "gap_share_pct",
    )
    list_filter = ("campaign", "kind", "day")
    search_fields = ("campaign__slug", "campaign_system__name")
    raw_id_fields = ("campaign", "campaign_system", "user")


@admin.register(CampaignOrderProgress)
class CampaignOrderProgressAdmin(admin.ModelAdmin):
    list_display = ("order", "user", "progress", "completed_at")
    list_filter = ("order__kind",)
    raw_id_fields = ("order", "user")


# --- Enlistment -------------------------------------------------------------


class CampaignEnlistmentPeriodInline(admin.TabularInline):
    model = CampaignEnlistmentPeriod
    extra = 0


class CampaignEnlistmentCharacterInline(admin.TabularInline):
    model = CampaignEnlistmentCharacter
    extra = 0
    raw_id_fields = ("character",)
    show_change_link = True


@admin.register(CampaignEnlistment)
class CampaignEnlistmentAdmin(admin.ModelAdmin):
    list_display = ("user", "campaign", "status", "source", "created_at")
    list_filter = ("campaign", "status", "source")
    search_fields = ("user__username", "campaign__slug")
    raw_id_fields = ("user", "campaign")
    inlines = [
        CampaignEnlistmentPeriodInline,
        CampaignEnlistmentCharacterInline,
    ]
    fieldsets = (
        (
            None,
            {
                "fields": ("campaign", "user", "status", "source"),
            },
        ),
        (
            "Notifications",
            {
                "classes": ("collapse",),
                "fields": (
                    "notify_gang_forming",
                    "notify_standing_fleet",
                    "notify_activity_nearby",
                    "notify_streak_at_risk",
                    "notify_fleets",
                    "notify_thresholds",
                    "notify_digest",
                    "digest_hour",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(CampaignEnlistmentCharacter)
class CampaignEnlistmentCharacterAdmin(admin.ModelAdmin):
    list_display = (
        "character",
        "enlistment",
        "included_from",
        "included_until",
        "payouts_polled_at",
    )
    list_filter = ("enlistment__campaign",)
    search_fields = ("character__character_name",)
    raw_id_fields = ("enlistment", "character")


@admin.register(CampaignEnlistmentPeriod)
class CampaignEnlistmentPeriodAdmin(admin.ModelAdmin):
    list_display = ("enlistment", "enlisted_at", "left_at")
    raw_id_fields = ("enlistment",)


# --- Activity (mostly read-only) --------------------------------------------


class CampaignKillmailParticipantInline(admin.TabularInline):
    model = CampaignKillmailParticipant
    extra = 0
    raw_id_fields = ("user",)
    fields = (
        "character_id",
        "character_name",
        "user",
        "role",
        "enlisted",
        "final_blow",
    )
    readonly_fields = ("role",)


@admin.register(CampaignKillmail)
class CampaignKillmailAdmin(admin.ModelAdmin):
    list_display = (
        "killmail_id",
        "campaign",
        "outcome",
        "killmail_time",
        "isk_value",
        "is_structure",
        "is_capital",
        "enlisted_attacker_count",
    )
    list_filter = ("campaign", "outcome", "is_structure", "is_capital")
    search_fields = ("killmail_id",)
    raw_id_fields = ("campaign", "structure", "fleet")
    readonly_fields = ("first_seen_via",)
    inlines = [CampaignKillmailParticipantInline]
    date_hierarchy = "killmail_time"


@admin.register(CampaignKillmailParticipant)
class CampaignKillmailParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "killmail",
        "user",
        "character_name",
        "character_id",
        "role",
    )
    list_filter = ("role",)
    raw_id_fields = ("killmail", "user")


@admin.register(CampaignSiteCompletion)
class CampaignSiteCompletionAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_at",
        "campaign",
        "site_kind",
        "amount_lp",
        "event_code",
        "user",
        "scored",
    )
    list_filter = ("campaign", "site_kind", "event_code", "scored")
    search_fields = ("user__username",)
    raw_id_fields = (
        "campaign",
        "campaign_system",
        "user",
        "payout",
        "complex",
    )
    date_hierarchy = "occurred_at"


@admin.register(CampaignComplexCompletion)
class CampaignComplexCompletionAdmin(admin.ModelAdmin):
    list_display = (
        "completed_at",
        "campaign_system",
        "inferred_plex_class",
        "base_lp_tier",
        "confidence",
        "split_count",
    )
    list_filter = ("confidence", "operational_state")
    raw_id_fields = ("campaign", "campaign_system")


@admin.register(CampaignSystemSnapshot)
class CampaignSystemSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "campaign_system",
        "captured_at",
        "contested_percent",
        "victory_points",
        "operational_state",
    )
    list_filter = ("operational_state", "campaign_system__campaign")
    raw_id_fields = ("campaign_system",)
    date_hierarchy = "captured_at"


@admin.register(CampaignAdvantageReading)
class CampaignAdvantageReadingAdmin(admin.ModelAdmin):
    list_display = (
        "campaign_system",
        "reported_at",
        "our_pct",
        "enemy_pct",
        "status",
        "source",
        "reported_by",
    )
    list_filter = ("status", "source")
    raw_id_fields = ("campaign_system", "reported_by")
    date_hierarchy = "reported_at"


@admin.register(CampaignAdvantageState)
class CampaignAdvantageStateAdmin(admin.ModelAdmin):
    list_display = (
        "campaign_system",
        "our_pct",
        "enemy_pct",
        "basis",
        "reading_age_minutes",
        "as_of",
    )
    list_filter = ("basis",)
    raw_id_fields = ("campaign_system",)


@admin.register(CampaignParticipantDay)
class CampaignParticipantDayAdmin(admin.ModelAdmin):
    list_display = (
        "day",
        "user",
        "campaign",
        "points",
        "kills",
        "structure_kills",
        "complexes",
        "active",
    )
    list_filter = ("campaign", "day", "active")
    search_fields = ("user__username",)
    raw_id_fields = ("campaign", "user")
    date_hierarchy = "day"


@admin.register(CampaignParticipantStat)
class CampaignParticipantStatAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "campaign",
        "points",
        "rank_points",
        "streak_days",
        "characters_tracked",
    )
    list_filter = ("campaign",)
    search_fields = ("user__username",)
    raw_id_fields = ("campaign", "user")


@admin.register(CampaignEvent)
class CampaignEventAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_at",
        "campaign",
        "kind",
        "title",
        "side",
        "source",
    )
    list_filter = ("campaign", "kind", "side", "source")
    search_fields = ("title", "body")
    raw_id_fields = (
        "campaign",
        "campaign_system",
        "user",
        "feed_event",
        "fleet",
    )
    date_hierarchy = "occurred_at"


@admin.register(CampaignAward)
class CampaignAwardAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "code",
        "user",
        "campaign",
        "scope",
        "week_start",
        "awarded_at",
    )
    list_filter = ("campaign", "scope", "code")
    search_fields = ("label", "user__username")
    raw_id_fields = ("campaign", "user")
    date_hierarchy = "awarded_at"
