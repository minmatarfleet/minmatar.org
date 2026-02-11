from django.contrib import admin
from django.utils.html import format_html

from industry.models import (
    IndustryOrder,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)


class IndustryOrderItemInline(admin.TabularInline):
    model = IndustryOrderItem
    extra = 1
    raw_id_fields = ("eve_type",)


@admin.register(IndustryOrder)
class IndustryOrderAdmin(admin.ModelAdmin):
    """Admin for industry orders (created_at, needed_by, character, inline items)."""

    list_display = (
        "id",
        "created_at",
        "needed_by",
        "character",
        "items_summary",
    )
    list_filter = ("character", "needed_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    autocomplete_fields = ("character",)
    inlines = [IndustryOrderItemInline]
    readonly_fields = ("created_at",)
    search_fields = ("id", "character__character_name")

    @admin.display(description="Items")
    def items_summary(self, obj):
        if not obj.pk:
            return "—"
        count = obj.items.count()
        return format_html("{} line(s)", count)


class IndustryOrderItemAssignmentInline(admin.TabularInline):
    model = IndustryOrderItemAssignment
    extra = 0
    autocomplete_fields = ("character",)


@admin.register(IndustryOrderItem)
class IndustryOrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "eve_type", "quantity")
    list_filter = ("order",)
    raw_id_fields = ("eve_type",)
    autocomplete_fields = ("order",)
    inlines = [IndustryOrderItemAssignmentInline]
    search_fields = ("order__id", "eve_type__name")


@admin.register(IndustryOrderItemAssignment)
class IndustryOrderItemAssignmentAdmin(admin.ModelAdmin):
    list_display = ("order_item", "character", "quantity")
    list_filter = ("character",)
    autocomplete_fields = ("order_item", "character")
