"""Corporation history Django admin."""

from django.contrib import admin

from eveonline.models import (
    EveCharacterCorporationHistory,
    EveCorporationAllianceHistory,
)


@admin.register(EveCharacterCorporationHistory)
class EveCharacterCorporationHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "character",
        "corporation_id",
        "start_date",
        "alliance_id",
        "faction_id",
        "record_id",
        "is_deleted",
    )
    list_filter = ("is_deleted",)
    search_fields = (
        "character__character_name",
        "=character__character_id",
        "=corporation_id",
        "=alliance_id",
    )
    readonly_fields = (
        "character",
        "record_id",
        "corporation_id",
        "start_date",
        "is_deleted",
        "alliance_id",
        "faction_id",
        "created_at",
        "updated_at",
    )
    raw_id_fields = ("character",)
    date_hierarchy = "start_date"


@admin.register(EveCorporationAllianceHistory)
class EveCorporationAllianceHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "corporation_id",
        "alliance_id",
        "start_date",
        "record_id",
        "is_deleted",
    )
    list_filter = ("is_deleted",)
    search_fields = ("=corporation_id", "=alliance_id")
    readonly_fields = (
        "corporation_id",
        "record_id",
        "alliance_id",
        "start_date",
        "is_deleted",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "start_date"
