from django.contrib import admin

from .models import (
    BuybackAcceptedItem,
    BuybackHangarSnapshot,
    BuybackLedgerEntry,
    BuybackPurchaseOrder,
    BuybackPurchaseOrderLine,
    EveBuybackSettings,
)


@admin.register(EveBuybackSettings)
class EveBuybackSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "assignee_name",
        "location",
        "active",
        "updated_at",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "active",
                    "assignee_name",
                    "location",
                    "leading_text",
                    "discord_thread_url",
                )
            },
        ),
        (
            "Rates",
            {
                "fields": (
                    "demand_jita_buy",
                    "surplus_jita_buy",
                    "ore_refine",
                ),
                "description": (
                    "Jita buy shares: 1.0 = pay full guide price. "
                    "Ore refine is the assumed yield for compressed ore."
                ),
            },
        ),
        (
            "What we buy",
            {
                "fields": (
                    "accepted_categories",
                    "exclusions",
                ),
                "description": (
                    "Category bullets are summary copy. Appraisal acceptance "
                    "is controlled by Buyback accepted items."
                ),
            },
        ),
        (
            "Hangar sales",
            {
                "fields": (
                    "sell_price_basis",
                    "sell_markup",
                ),
                "description": (
                    "Jita split is the midpoint of live Jita buy and sell. "
                    "Markup is an extra share (0 = none, 0.05 = 5%)."
                ),
            },
        ),
        (
            "Stockpile hangars",
            {
                "fields": (
                    "stockpile_structure_id",
                    "stockpile_office_id",
                    "stockpile_hangar_flag",
                    "stockpile_include_deliveries",
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return not EveBuybackSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BuybackAcceptedItem)
class BuybackAcceptedItemAdmin(admin.ModelAdmin):
    list_display = (
        "eve_type",
        "category",
        "active",
        "demand_status",
        "demand_quantity",
        "stockpile_quantity",
        "metrics_updated_at",
        "created_at",
    )
    list_filter = ("category", "active", "demand_status")
    search_fields = ("eve_type__name",)
    autocomplete_fields = ("eve_type",)
    list_editable = ("active",)


@admin.register(BuybackLedgerEntry)
class BuybackLedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_at",
        "reason",
        "eve_type",
        "quantity",
        "counterparty_name",
        "source_id",
        "isk_total",
    )
    list_filter = ("reason",)
    search_fields = ("eve_type__name", "source_id")
    autocomplete_fields = ("eve_type",)
    readonly_fields = ("created_at",)


@admin.register(BuybackHangarSnapshot)
class BuybackHangarSnapshotAdmin(admin.ModelAdmin):
    list_display = ("taken_at", "created_at")
    readonly_fields = ("taken_at", "quantities", "created_at")


class BuybackPurchaseOrderLineInline(admin.TabularInline):
    model = BuybackPurchaseOrderLine
    extra = 0
    autocomplete_fields = ("eve_type",)
    readonly_fields = (
        "eve_type",
        "name",
        "quantity",
        "unit_price",
        "line_total",
        "fill_source",
    )


@admin.register(BuybackPurchaseOrder)
class BuybackPurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "character_name",
        "contract_total",
        "source",
        "created_at",
    )
    list_filter = ("status", "source")
    search_fields = ("character_name", "created_by__username")
    readonly_fields = (
        "created_by",
        "character_id",
        "character_name",
        "paste",
        "contract_total",
        "sell_price_basis",
        "sell_markup",
        "created_at",
        "updated_at",
        "completed_at",
        "completed_by",
        "discord_thread_id",
    )
    inlines = (BuybackPurchaseOrderLineInline,)
