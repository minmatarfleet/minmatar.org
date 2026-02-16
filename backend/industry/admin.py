from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from industry.models import (
    IndustryOrder,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)


class IndustryOrderItemInline(admin.TabularInline):
    """Order items with a link to manage assignments for each item."""

    model = IndustryOrderItem
    extra = 1
    raw_id_fields = ("eve_type",)
    fields = ("eve_type", "quantity", "assignments_link")
    readonly_fields = ("assignments_link",)

    @admin.display(description="Assignments")
    def assignments_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("admin:industry_industryorderitem_change", args=[obj.pk])
        return format_html('<a href="{}">Manage assignments</a>', url)


@admin.register(IndustryOrder)
class IndustryOrderAdmin(admin.ModelAdmin):
    """Industry orders: manage order items and their assignments from one place."""

    list_display = (
        "id",
        "created_at",
        "needed_by",
        "fulfilled_at",
        "character",
        "items_summary",
    )
    list_filter = ("character", "needed_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    autocomplete_fields = ("character",)
    inlines = [IndustryOrderItemInline]
    readonly_fields = ("created_at", "fulfilled_at", "mark_fulfilled_button")
    search_fields = ("id", "character__character_name")
    fieldsets = (
        (None, {"fields": ("character", "needed_by", "created_at")}),
        (
            "Fulfilment",
            {
                "fields": ("fulfilled_at", "mark_fulfilled_button"),
            },
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                "<path:object_id>/mark-fulfilled/",
                self.admin_site.admin_view(self.mark_fulfilled_view),
                name="industry_industryorder_mark_fulfilled",
            ),
        ] + urls

    def mark_fulfilled_view(self, request, object_id):
        if not self.has_change_permission(request):
            messages.error(request, "Permission denied.")
            return HttpResponseRedirect("../")
        obj = self.get_object(request, object_id)
        if not obj:
            messages.error(request, "Order not found.")
            return HttpResponseRedirect("../")
        obj.fulfilled_at = timezone.now()
        obj.save(update_fields=["fulfilled_at"])
        messages.success(request, "Order marked as fulfilled.")
        return HttpResponseRedirect("../")

    @admin.display(description="Mark as fulfilled")
    def mark_fulfilled_button(self, obj):
        if not obj.pk or obj.fulfilled_at is not None:
            return "—"
        url = reverse(
            "admin:industry_industryorder_mark_fulfilled", args=[obj.pk]
        )
        return format_html(
            '<a class="button" href="{}">Mark order as fulfilled</a>', url
        )

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
    """Order item detail: manage assignments. Reached via "Manage assignments" on the order."""

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


# ----- Industry admin index: only Orders -----

INDUSTRY_INDEX_MODELS = {"industryorder": "Orders"}


def _industry_get_app_list(request):
    """Show industry app with only Orders in the index."""
    app_list = _industry_previous_get_app_list(request)
    for app in app_list:
        if app["app_label"] != "industry":
            continue
        models = [
            {**m, "name": INDUSTRY_INDEX_MODELS[m["object_name"].lower()]}
            for m in app["models"]
            if m["object_name"].lower() in INDUSTRY_INDEX_MODELS
        ]
        if models:
            app["models"] = models
        break
    return app_list


_industry_previous_get_app_list = admin.site.get_app_list
admin.site.get_app_list = _industry_get_app_list
