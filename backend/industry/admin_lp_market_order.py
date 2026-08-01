"""Admin for LP buyback market orders."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from industry.models import (
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointMarketOrderClaim,
)


class IndustryLoyaltyPointMarketOrderClaimInline(admin.TabularInline):
    model = IndustryLoyaltyPointMarketOrderClaim
    extra = 0
    autocomplete_fields = ("claimed_by",)
    readonly_fields = ("created_at",)
    fields = (
        "amount",
        "destination_character_name",
        "destination_corporation_name",
        "claimed_by",
        "created_at",
    )


@admin.register(IndustryLoyaltyPointMarketOrder)
class IndustryLoyaltyPointMarketOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "side",
        "loyalty_point",
        "quantity",
        "isk_per_lp",
        "total_isk_display",
        "status",
        "created_by",
        "claimed_by",
        "created_at",
    )
    list_filter = ("side", "status", "loyalty_point")
    search_fields = (
        "destination_character_name",
        "notes",
        "created_by__username",
        "claimed_by__username",
        "loyalty_point__name",
    )
    autocomplete_fields = ("loyalty_point", "created_by", "claimed_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    inlines = (IndustryLoyaltyPointMarketOrderClaimInline,)
    readonly_fields = (
        "total_isk_display",
        "ledger_entries_link",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "loyalty_point",
                    "side",
                    "quantity",
                    "isk_per_lp",
                    "total_isk_display",
                    "status",
                    "notes",
                ),
                "description": (
                    "Public buyback book row. Completing a sell typically posts "
                    "a stockpile ledger credit with seller and counterparty."
                ),
            },
        ),
        (
            "Parties",
            {
                "fields": (
                    "created_by",
                    "claimed_by",
                    "destination_character_name",
                ),
            },
        ),
        (
            "Discord & ledger",
            {
                "fields": ("discord_thread_id", "ledger_entries_link"),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at", "completed_at"),
            },
        ),
    )

    @admin.display(description="total ISK")
    def total_isk_display(self, obj):
        if obj.quantity is None or obj.isk_per_lp is None:
            return "—"
        return f"{obj.quantity * obj.isk_per_lp:,}"

    @admin.display(description="ledger entries")
    def ledger_entries_link(self, obj):
        if not obj.pk:
            return "—"
        count = obj.ledger_entries.count()
        url = reverse(
            "admin:industry_industryloyaltypointledgerentry_changelist"
        )
        return format_html(
            '<a href="{}?market_order__id__exact={}">{} entr{}</a>',
            url,
            obj.pk,
            count,
            "y" if count == 1 else "ies",
        )
