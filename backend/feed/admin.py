from django.contrib import admin

from feed.models import (
    FeedCharacterAffiliation,
    FeedCluster,
    FeedEvent,
    FeedEventFleetLink,
    FeedEventKillmailLink,
    FeedKillmail,
    FeedMonitoredSystem,
    FeedR2z2Cursor,
    FeedRollupConfig,
    FeedSystemContestedSnapshot,
)


@admin.register(FeedMonitoredSystem)
class FeedMonitoredSystemAdmin(admin.ModelAdmin):
    list_display = ("name", "solar_system_id", "source", "is_active")
    list_filter = ("source", "is_active")
    search_fields = ("name", "solar_system_id")


@admin.register(FeedSystemContestedSnapshot)
class FeedSystemContestedSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "solar_system_id",
        "contested_percent",
        "occupier_faction_id",
        "captured_at",
    )
    list_filter = ("occupier_faction_id",)
    search_fields = ("solar_system_id",)


@admin.register(FeedKillmail)
class FeedKillmailAdmin(admin.ModelAdmin):
    list_display = (
        "killmail_id",
        "killmail_time",
        "solar_system_id",
        "created_at",
    )
    list_filter = ("solar_system_id",)
    search_fields = ("killmail_id",)
    readonly_fields = ("raw_killmail", "zkb_meta", "attacker_summary")


@admin.register(FeedCharacterAffiliation)
class FeedCharacterAffiliationAdmin(admin.ModelAdmin):
    list_display = (
        "character_id",
        "faction_id",
        "corporation_id",
        "esi_checked_at",
    )
    list_filter = ("faction_id",)
    search_fields = ("character_id",)


@admin.register(FeedCluster)
class FeedClusterAdmin(admin.ModelAdmin):
    list_display = (
        "cluster_key",
        "cluster_type",
        "solar_system_id",
        "kill_count",
        "pilot_count",
        "is_active",
        "last_kill_at",
    )
    list_filter = ("cluster_type", "is_active")


@admin.register(FeedRollupConfig)
class FeedRollupConfigAdmin(admin.ModelAdmin):
    list_display = ("rollup_code", "is_enabled", "version", "updated_at")


@admin.register(FeedEvent)
class FeedEventAdmin(admin.ModelAdmin):
    list_display = (
        "kind",
        "title",
        "occurred_at",
        "accent",
        "rollup_code",
        "is_active",
    )
    list_filter = ("kind", "rollup_code", "accent", "is_active")
    search_fields = ("title", "cluster_key")


@admin.register(FeedR2z2Cursor)
class FeedR2z2CursorAdmin(admin.ModelAdmin):
    list_display = ("last_sequence_id", "updated_at")

    def has_add_permission(self, request):
        return not FeedR2z2Cursor.objects.exists()


admin.site.register(FeedEventKillmailLink)
admin.site.register(FeedEventFleetLink)
