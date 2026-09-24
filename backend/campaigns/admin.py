"""Django admin for live campaigns.

Operators configure theaters, structures, opponents, week targets and the
rest from here; the frontend cog opens the campaign change page.
"""

from django.contrib import admin, messages
from django.utils import timezone

from campaigns.services import plan
from campaigns.models import (
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
    CampaignOpponent,
    CampaignOrderProgress,
    CampaignParticipantDay,
    CampaignParticipantStat,
    CampaignSiteCompletion,
    CampaignStandingFleet,
    CampaignStructure,
    CampaignSystem,
    CampaignSystemArc,
    CampaignSystemInsurgency,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
)

# --- Inlines on Campaign ----------------------------------------------------


class CampaignSystemInline(admin.TabularInline):
    model = CampaignSystem
    extra = 0
    show_change_link = True
    fields = (
        "name",
        "solar_system_id",
        "region_id",
        "role",
        "priority",
        "goal",
        "is_fw_objective",
        "retired_at",
    )


class CampaignAreaInline(admin.TabularInline):
    model = CampaignArea
    extra = 0
    show_change_link = True
    fields = ("name", "scope", "constellation_id", "region_id")


class CampaignOpponentInline(admin.TabularInline):
    model = CampaignOpponent
    extra = 0
    show_change_link = True
    fields = (
        "name",
        "ticker",
        "alliance_id",
        "corporation_id",
        "faction_id",
    )


class CampaignStructureInline(admin.TabularInline):
    model = CampaignStructure
    extra = 0
    show_change_link = True
    fields = (
        "name",
        "structure_type",
        "system_name",
        "solar_system_id",
        "status",
        "source",
        "corporation_name",
        "alliance_name",
        "related_alliance_name",
        "reinforce_hour",
        "timer",
    )
    raw_id_fields = ("timer", "killmail", "created_by")
    readonly_fields = ("created_at",)


class CampaignFittingInline(admin.TabularInline):
    model = CampaignFitting
    extra = 0
    show_change_link = True
    fields = ("fitting", "role_label", "srp_eligible", "order")
    raw_id_fields = ("fitting",)


class CampaignStandingFleetInline(admin.StackedInline):
    model = CampaignStandingFleet
    extra = 0
    max_num = 1
    can_delete = True


# --- Campaign ---------------------------------------------------------------


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
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
    inlines = [
        CampaignSystemInline,
        CampaignAreaInline,
        CampaignOpponentInline,
        CampaignStructureInline,
        CampaignFittingInline,
        CampaignStandingFleetInline,
    ]
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
                "description": (
                    "Tagline is the one-line focus on the campaign list and "
                    "detail header. Description is the longer story under it."
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
                "classes": ("collapse",),
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
                "classes": ("collapse",),
                "fields": ("donation_corporation_id", "donation_division"),
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
    list_display = (
        "name",
        "campaign",
        "solar_system_id",
        "role",
        "priority",
        "goal",
        "is_fw_objective",
        "retired_at",
    )
    list_filter = (
        "campaign",
        "role",
        "priority",
        "goal",
        "is_fw_objective",
    )
    list_editable = ("role", "priority", "goal", "is_fw_objective")
    search_fields = ("name", "solar_system_id", "campaign__slug")
    raw_id_fields = ("campaign",)
    inlines = [CampaignSystemArcInline, CampaignWeekTargetInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "campaign",
                    "name",
                    "solar_system_id",
                    "region_id",
                ),
            },
        ),
        (
            "Theater role",
            {
                "fields": (
                    "is_fw_objective",
                    "goal",
                    "role",
                    "priority",
                    "added_at",
                    "retired_at",
                ),
                "description": (
                    "FW objectives drive plex/VP/advantage and kill scoring. "
                    "Ops theaters (is_fw_objective off) are for structure "
                    "hunting and member guidance only."
                ),
            },
        ),
    )


@admin.register(CampaignArea)
class CampaignAreaAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "scope",
        "campaign",
        "constellation_id",
        "region_id",
    )
    list_filter = ("campaign", "scope")
    search_fields = ("name", "campaign__slug")
    raw_id_fields = ("campaign",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "campaign",
                    "name",
                    "scope",
                    "constellation_id",
                    "region_id",
                ),
                "description": (
                    "Constellation or region ops theater. Never an FW "
                    "objective; guidance and structure hunting only."
                ),
            },
        ),
    )


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


# --- Structures and opponents -----------------------------------------------


@admin.register(CampaignOpponent)
class CampaignOpponentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "ticker",
        "campaign",
        "alliance_id",
        "corporation_id",
        "faction_id",
    )
    list_filter = ("campaign",)
    search_fields = ("name", "ticker", "alliance_id")
    raw_id_fields = ("campaign",)


@admin.register(CampaignStructure)
class CampaignStructureAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "structure_type",
        "system_name",
        "corporation_name",
        "related_alliance_name",
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
    readonly_fields = ("created_at", "updated_at")
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


@admin.register(CampaignStandingFleet)
class CampaignStandingFleetAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "advert_name",
        "member_count",
        "current_boss_character_id",
        "last_seen_at",
        "is_up_display",
    )
    search_fields = ("advert_name", "campaign__slug")
    raw_id_fields = ("campaign", "fleet", "current_boss_user")

    @admin.display(description="Up", boolean=True)
    def is_up_display(self, obj: CampaignStandingFleet) -> bool:
        return obj.is_up


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
