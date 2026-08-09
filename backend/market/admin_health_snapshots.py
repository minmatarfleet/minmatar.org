"""Read-only Django admin for market health snapshots."""

from django.contrib import admin

from market.models import EveMarketHealthSnapshot


@admin.register(EveMarketHealthSnapshot)
class EveMarketHealthSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "captured_at",
        "kind",
        "location",
        "health_pct",
        "viability_pct",
        "targets",
        "fulfilled",
    )
    list_display_links = ("captured_at", "location")
    list_filter = ("kind", "location")
    list_per_page = 50
    date_hierarchy = "captured_at"
    search_fields = ("location__location_name", "location__short_name")
    raw_id_fields = ("location",)
    ordering = ("-captured_at",)
    readonly_fields = (
        "captured_at",
        "kind",
        "location",
        "health_pct",
        "viability_pct",
        "targets",
        "listed_targets",
        "fulfilled",
        "viable_fulfilled",
        "isk",
        "synced_at",
        "history_days",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("location")
