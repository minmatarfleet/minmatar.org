from django.contrib import admin

from campaigns.models import (
    Campaign,
    CampaignAdvantageReading,
    CampaignAdvantageState,
    CampaignAward,
    CampaignComplexCompletion,
    CampaignDailyOrder,
    CampaignEnlistment,
    CampaignEnlistmentCharacter,
    CampaignEvent,
    CampaignKillmail,
    CampaignParticipantDay,
    CampaignParticipantStat,
    CampaignSiteCompletion,
    CampaignStandingFleet,
    CampaignSystem,
    CampaignSystemArc,
    CampaignSystemInsurgency,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
)


class CampaignSystemInline(admin.TabularInline):
    model = CampaignSystem
    extra = 0


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "short_code",
        "status",
        "start_at",
        "end_at",
    )
    list_filter = ("status",)
    search_fields = ("name", "slug", "short_code")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CampaignSystemInline]


@admin.register(CampaignSystem)
class CampaignSystemAdmin(admin.ModelAdmin):
    list_display = ("name", "campaign", "role", "goal", "solar_system_id")
    list_filter = ("campaign", "role", "goal")


@admin.register(CampaignWeekTarget)
class CampaignWeekTargetAdmin(admin.ModelAdmin):
    list_display = (
        "campaign_system",
        "week_start",
        "metric",
        "target",
        "progress",
        "proposed",
    )
    list_filter = ("week_start", "metric", "proposed")


@admin.register(CampaignEnlistment)
class CampaignEnlistmentAdmin(admin.ModelAdmin):
    list_display = ("user", "campaign", "status", "source", "created_at")
    list_filter = ("campaign", "status", "source")
    search_fields = ("user__username",)


@admin.register(CampaignKillmail)
class CampaignKillmailAdmin(admin.ModelAdmin):
    list_display = (
        "killmail_id",
        "campaign",
        "outcome",
        "killmail_time",
        "isk_value",
        "enlisted_attacker_count",
    )
    list_filter = ("campaign", "outcome")
    search_fields = ("killmail_id",)


@admin.register(CampaignSiteCompletion)
class CampaignSiteCompletionAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_at",
        "campaign",
        "site_kind",
        "amount_lp",
        "event_code",
        "user",
    )
    list_filter = ("campaign", "site_kind", "event_code")


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


@admin.register(CampaignParticipantDay)
class CampaignParticipantDayAdmin(admin.ModelAdmin):
    list_display = ("day", "user", "campaign", "points", "kills", "complexes")
    list_filter = ("campaign", "day", "active")


@admin.register(CampaignParticipantStat)
class CampaignParticipantStatAdmin(admin.ModelAdmin):
    list_display = ("user", "campaign", "points", "rank_points", "streak_days")
    list_filter = ("campaign",)


@admin.register(CampaignEvent)
class CampaignEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "campaign", "kind", "title", "side")
    list_filter = ("campaign", "kind", "side", "source")


admin.site.register(CampaignSystemArc)
admin.site.register(CampaignSystemInsurgency)
admin.site.register(CampaignSystemSnapshot)
admin.site.register(CampaignAdvantageReading)
admin.site.register(CampaignAdvantageState)
admin.site.register(CampaignDailyOrder)
admin.site.register(CampaignEnlistmentCharacter)
admin.site.register(CampaignStandingFleet)
admin.site.register(CampaignAward)
