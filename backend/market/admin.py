from django.contrib import admin
from django.contrib import messages
from django.db.models import Count, Sum
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.http import urlencode

from eveonline.models import EveLocation

from market.models import (
    EveMarketContract,
    EveMarketContractError,
    EveMarketContractExpectation,
    EveMarketContractResponsibility,
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
    EveMarketItemHistory,
    EveMarketItemOrder,
    EveMarketItemResponsibility,
    EveMarketItemTransaction,
    EveTypeWithSellOrders,
)
from market.models.item import parse_eft_items
from market.tasks import fetch_market_item_history_for_type

# Only these two appear in the Market admin index
MARKET_INDEX_MODELS = {
    "evemarketcontractexpectation": "Market contracts",
    "evemarketfittingexpectation": "Market fitting expectations",
    "evetypewithsellorders": "Market sell orders",
}


def get_market_item_trends(item_id):
    """Build trend data for one item across all price-active location regions: dates × regions (average)."""
    locations = list(
        EveLocation.objects.filter(
            prices_active=True, region_id__isnull=False
        ).order_by("location_name")
    )
    if not locations:
        return None
    region_ids = [loc.region_id for loc in locations]
    qs = (
        EveMarketItemHistory.objects.filter(
            item_id=item_id, region_id__in=region_ids
        )
        .values("date", "region_id", "average", "volume")
        .order_by("-date")[: 30 * len(region_ids)]
    )
    by_date_region = {}
    for row in qs:
        by_date_region[(row["date"], row["region_id"])] = {
            "average": row["average"],
            "volume": row["volume"],
        }
    dates = sorted(
        {d for (d, _) in by_date_region},
        reverse=True,
    )[:30]
    rows = []
    for date in dates:
        cells = []
        for loc in locations:
            data = by_date_region.get((date, loc.region_id))
            cells.append(
                {"average": data["average"], "volume": data["volume"]}
                if data
                else None
            )
        rows.append({"date": date, "cells": cells})
    return {
        "locations": locations,
        "rows": rows,
    }


# ----- Contracts -----


class EveMarketContractResponsibilityInline(admin.TabularInline):
    model = EveMarketContractResponsibility
    extra = 0


@admin.register(EveMarketContractExpectation)
class EveMarketContractExpectationAdmin(admin.ModelAdmin):
    """Contract expectations: fitting + quantity per location; stock levels from outstanding contracts."""

    list_display = (
        "fitting",
        "location",
        "quantity",
        "current_quantity",
        "is_fulfilled",
        "is_understocked",
    )
    list_display_links = ("fitting", "location")
    search_fields = (
        "fitting__name",
        "fitting__description",
        "location__location_name",
        "location__short_name",
    )
    list_filter = ("location", "fitting")
    list_per_page = 50
    readonly_fields = (
        "current_quantity",
        "desired_quantity",
        "is_fulfilled",
        "is_understocked",
        "view_outstanding_contracts_link",
    )
    autocomplete_fields = ("fitting", "location")
    ordering = ("fitting__name", "location__location_name")
    inlines = [EveMarketContractResponsibilityInline]
    fieldsets = (
        ("Details", {"fields": ("fitting", "location", "quantity")}),
        (
            "Status",
            {
                "fields": (
                    "current_quantity",
                    "desired_quantity",
                    "is_fulfilled",
                    "is_understocked",
                    "view_outstanding_contracts_link",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Outstanding contracts")
    def view_outstanding_contracts_link(self, obj):
        if not obj.pk or not obj.fitting_id or not obj.location_id:
            return "–"
        query = {
            "fitting__id": obj.fitting_id,
            "location__id": obj.location_id,
            "status__exact": "outstanding",
        }
        url = (
            reverse("admin:market_evemarketcontract_changelist")
            + "?"
            + urlencode(query)
        )
        return format_html('<a href="{}">View outstanding contracts</a>', url)


@admin.register(EveMarketContractResponsibility)
class EveMarketContractResponsibilityAdmin(admin.ModelAdmin):
    """Who is responsible for fulfilling a contract expectation (character or corp ID)."""

    list_display = ("expectation", "entity_id", "get_fitting", "get_location")
    list_display_links = ("expectation",)
    search_fields = (
        "entity_id",
        "expectation__fitting__name",
        "expectation__location__location_name",
    )
    list_filter = ("expectation__location", "expectation__fitting")
    list_per_page = 50
    autocomplete_fields = ("expectation",)

    @admin.display(description="Fitting")
    def get_fitting(self, obj):
        return obj.expectation.fitting.name

    @admin.display(description="Location")
    def get_location(self, obj):
        return obj.expectation.location.location_name


@admin.register(EveMarketContract)
class EveMarketContractAdmin(admin.ModelAdmin):
    """Market contracts (item exchange), synced from ESI."""

    list_display = (
        "id",
        "title",
        "status",
        "fitting",
        "location",
        "issuer_external_id",
        "price",
        "created_at",
    )
    list_display_links = ("id", "title")
    search_fields = (
        "title",
        "id",
        "issuer_external_id",
        "fitting__name",
        "location__location_name",
    )
    list_filter = (
        "status",
        "is_public",
        "location",
        "fitting",
        "created_at",
    )
    list_per_page = 50
    readonly_fields = (
        "created_at",
        "completed_at",
        "last_updated",
        "issued_at",
        "expires_at",
    )
    date_hierarchy = "created_at"
    autocomplete_fields = ("location", "fitting")
    fieldsets = (
        (
            "Contract Details",
            {"fields": ("id", "title", "status", "price", "is_public")},
        ),
        (
            "Parties",
            {"fields": ("issuer_external_id", "assignee_id", "acceptor_id")},
        ),
        ("Relationships", {"fields": ("location", "fitting")}),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "issued_at",
                    "expires_at",
                    "completed_at",
                    "last_updated",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(EveMarketContractError)
class EveMarketContractErrorAdmin(admin.ModelAdmin):
    """Contract parse/validation errors (e.g. unknown fitting or location)."""

    list_display = ("title", "issuer", "location", "quantity", "updated_at")
    list_display_links = ("title",)
    search_fields = (
        "title",
        "issuer__character_name",
        "location__location_name",
        "location__short_name",
    )
    list_filter = ("location", "updated_at")
    list_per_page = 50
    readonly_fields = ("updated_at",)
    date_hierarchy = "updated_at"
    autocomplete_fields = ("issuer", "location")


# ----- Fitting expectations (decomposed into items) -----


@admin.register(EveMarketFittingExpectation)
class EveMarketFittingExpectationAdmin(admin.ModelAdmin):
    """Fitting expectations: a fitting × quantity per location, decomposed into item-level expectations."""

    list_display = (
        "fitting",
        "location",
        "quantity",
        "get_item_count",
    )
    list_display_links = ("fitting", "location")
    search_fields = (
        "fitting__name",
        "location__location_name",
        "location__short_name",
    )
    list_filter = ("location", "fitting")
    list_per_page = 50
    autocomplete_fields = ("fitting", "location")
    ordering = ("fitting__name", "location__location_name")
    readonly_fields = ("get_decomposed_items",)
    fieldsets = (
        ("Details", {"fields": ("fitting", "location", "quantity")}),
        (
            "Decomposed items",
            {
                "fields": ("get_decomposed_items",),
            },
        ),
    )

    @admin.display(description="Unique items")
    def get_item_count(self, obj):
        return len(parse_eft_items(obj.fitting.eft_format))

    @admin.display(description="Items from fitting")
    def get_decomposed_items(self, obj):
        if not obj.pk:
            return "–"
        items = obj.get_item_quantities()
        rows = sorted(items.items(), key=lambda kv: kv[0])
        lines = [f"{name} × {qty}" for name, qty in rows]
        return format_html("<br>".join(lines))


# ----- Market sell orders (unique EVE types with sell orders) -----


class SellOrderLocationFilter(admin.SimpleListFilter):
    """Filter EVE types by location (only types that have a sell order at the selected location)."""

    title = "location"
    parameter_name = "location"

    def lookups(self, request, model_admin):
        location_ids = EveMarketItemOrder.objects.values_list(
            "location_id", flat=True
        ).distinct()
        locations = EveLocation.objects.filter(pk__in=location_ids).order_by(
            "location_name"
        )
        return [(loc.pk, loc.location_name) for loc in locations]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                evemarketitemorder__location_id=self.value()
            ).distinct()
        return queryset


@admin.register(EveTypeWithSellOrders)
class EveTypeWithSellOrdersAdmin(admin.ModelAdmin):
    """Unique EVE types we have sell orders for; drill in to see history and stock per location."""

    list_display = ("name", "get_order_count", "get_location_count")
    list_display_links = ("name",)
    list_filter = (SellOrderLocationFilter,)
    search_fields = ("name",)
    list_per_page = 50
    ordering = ("name",)
    change_form_template = (
        "admin/market/evetypewithsellorders/change_form.html"
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _order_count=Count("evemarketitemorder"),
                _location_count=Count(
                    "evemarketitemorder__location", distinct=True
                ),
            )
        )

    @admin.display(description="Orders", ordering="_order_count")
    def get_order_count(self, obj):
        return getattr(obj, "_order_count", "–")

    @admin.display(description="Locations", ordering="_location_count")
    def get_location_count(self, obj):
        return getattr(obj, "_location_count", "–")

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                "<path:object_id>/fetch-history/",
                self.admin_site.admin_view(self.fetch_history_view),
                name="market_evetypewithsellorders_fetch_history",
            ),
        ] + urls

    def fetch_history_view(self, request, object_id):
        if not self.has_change_permission(request):
            messages.error(request, "Permission denied.")
            return HttpResponseRedirect("../")
        obj = self.get_object(request, object_id)
        if not obj:
            messages.error(request, "Item not found.")
            return HttpResponseRedirect("../")
        fetch_market_item_history_for_type.delay(obj.pk)
        messages.success(
            request,
            f"Market history fetch queued for {obj.name} (type_id={obj.pk}). "
            "It will run across all regions.",
        )
        return HttpResponseRedirect("../")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj:
            extra_context["market_item_name"] = str(obj)
            extra_context["market_item_trends"] = get_market_item_trends(
                obj.pk
            )
            extra_context["fetch_history_url"] = "../fetch-history/"
            expectations = list(
                EveMarketItemExpectation.objects.filter(item_id=obj.pk)
                .select_related("location")
                .order_by("location__location_name")
            )
            extra_context["expectations_for_item"] = expectations
            expectation_location_ids = {e.location_id for e in expectations}
            other = (
                EveMarketItemOrder.objects.filter(item_id=obj.pk)
                .exclude(location_id__in=expectation_location_ids)
                .values("location__location_name")
                .annotate(total=Sum("quantity"))
                .order_by("location__location_name")
            )
            extra_context["other_locations_with_orders"] = [
                {
                    "location_name": r["location__location_name"],
                    "total": r["total"],
                }
                for r in other
            ]
        return super().change_view(request, object_id, form_url, extra_context)


# ----- Items (sell-order seeding; hidden from index) -----


class EveMarketItemResponsibilityInline(admin.TabularInline):
    model = EveMarketItemResponsibility
    extra = 0


@admin.register(EveMarketItemExpectation)
class EveMarketItemExpectationAdmin(admin.ModelAdmin):
    """Item seeding: EVE type + target quantity per location, tracked on sell orders."""

    list_display = (
        "item",
        "location",
        "quantity",
        "current_quantity",
        "is_fulfilled",
        "is_understocked",
    )
    list_display_links = ("item", "location")
    search_fields = (
        "item__name",
        "location__location_name",
        "location__short_name",
    )
    list_filter = ("location", "item")
    list_per_page = 50
    autocomplete_fields = ("location",)
    raw_id_fields = ("item",)
    readonly_fields = (
        "current_quantity",
        "desired_quantity",
        "is_fulfilled",
        "is_understocked",
    )
    ordering = ("item__name", "location__location_name")
    inlines = [EveMarketItemResponsibilityInline]
    change_form_template = "admin/market/evemarketitemorder/change_form.html"
    fieldsets = (
        ("Details", {"fields": ("item", "location", "quantity")}),
        (
            "Status (from sell orders)",
            {
                "fields": (
                    "current_quantity",
                    "desired_quantity",
                    "is_fulfilled",
                    "is_understocked",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj and obj.item_id:
            extra_context["market_item_trends"] = get_market_item_trends(
                obj.item_id
            )
            extra_context["market_item_name"] = str(obj.item)
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(EveMarketItemResponsibility)
class EveMarketItemResponsibilityAdmin(admin.ModelAdmin):
    """Who is responsible for fulfilling an item expectation (character or corp ID)."""

    list_display = ("expectation", "entity_id", "get_item", "get_location")
    list_display_links = ("expectation",)
    search_fields = (
        "entity_id",
        "expectation__item__name",
        "expectation__location__location_name",
    )
    list_filter = ("expectation__location", "expectation__item")
    list_per_page = 50
    autocomplete_fields = ("expectation",)

    @admin.display(description="Item")
    def get_item(self, obj):
        return obj.expectation.item.name

    @admin.display(description="Location")
    def get_location(self, obj):
        return obj.expectation.location.location_name


@admin.register(EveMarketItemOrder)
class EveMarketItemOrderAdmin(admin.ModelAdmin):
    """Sell orders at structures, synced from ESI for item seeding."""

    list_display = (
        "order_id",
        "item",
        "location",
        "price",
        "quantity",
        "issuer_external_id",
        "imported_by_task_uid",
        "imported_page",
    )
    list_display_links = ("item", "location")
    list_filter = ("location", "item")
    list_per_page = 50
    show_full_result_count = False
    search_fields = (
        "item__name",
        "location__location_name",
        "location__short_name",
    )
    autocomplete_fields = ("location",)
    raw_id_fields = ("item",)
    ordering = ("location__location_name", "item__name")
    change_form_template = "admin/market/evemarketitemorder/change_form.html"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("item", "location")

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                "<path:object_id>/fetch-history/",
                self.admin_site.admin_view(self.fetch_history_view),
                name="market_evemarketitemorder_fetch_history",
            ),
        ] + urls

    def fetch_history_view(self, request, object_id):
        if not self.has_change_permission(request):
            messages.error(request, "Permission denied.")
            return HttpResponseRedirect("../")
        obj = self.get_object(request, object_id)
        if not obj:
            messages.error(request, "Order not found.")
            return HttpResponseRedirect("../")
        if not obj.item_id:
            messages.error(request, "Order has no item.")
            return HttpResponseRedirect("../")
        fetch_market_item_history_for_type.delay(obj.item_id)
        messages.success(
            request,
            f"Market history fetch queued for item {obj.item} (type_id={obj.item_id}). "
            "It will run across all regions.",
        )
        return HttpResponseRedirect("../")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj and obj.item_id:
            extra_context["market_item_trends"] = get_market_item_trends(
                obj.item_id
            )
            extra_context["market_item_name"] = str(obj.item)
            extra_context["fetch_history_url"] = "../fetch-history/"
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(EveMarketItemTransaction)
class EveMarketItemTransactionAdmin(admin.ModelAdmin):
    """Market transactions (for future use)."""

    list_display = (
        "item",
        "location",
        "price",
        "quantity",
        "issuer_external_id",
        "sell_date",
    )
    list_display_links = ("item", "location")
    list_filter = ("location", "item")
    list_per_page = 100
    date_hierarchy = "sell_date"
    search_fields = (
        "item__name",
        "location__location_name",
        "location__short_name",
    )
    autocomplete_fields = ("location",)
    raw_id_fields = ("item",)
    ordering = ("-sell_date", "location__location_name", "item__name")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("item", "location")


@admin.register(EveMarketItemHistory)
class EveMarketItemHistoryAdmin(admin.ModelAdmin):
    """Daily region market history (raw). For trends by item, use Sell orders → open an order → see trends."""

    list_display = (
        "region_id",
        "item",
        "date",
        "average",
        "highest",
        "lowest",
        "order_count",
        "volume",
    )
    list_display_links = ("region_id", "item", "date")
    list_filter = ("region_id", "item")
    list_per_page = 100
    date_hierarchy = "date"
    search_fields = ("item__name",)
    raw_id_fields = ("item",)
    ordering = ("-date", "region_id", "item__name")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("item")


# ----- Market admin index: only Contracts + Sell orders -----


def _market_get_app_list(request):
    """Show a single Market section with only Market contracts and Market sell orders."""
    app_list = admin.site.get_app_list_original(request)
    for app in app_list:
        if app["app_label"] != "market":
            continue
        models = []
        for m in app["models"]:
            key = m["object_name"].lower()
            if key in MARKET_INDEX_MODELS:
                display_name = MARKET_INDEX_MODELS[key]
                models.append({**m, "name": display_name})
        if models:
            app["models"] = models
        break
    return app_list


if not hasattr(admin.site, "get_app_list_original"):
    admin.site.get_app_list_original = admin.site.get_app_list  # bound method
    admin.site.get_app_list = _market_get_app_list
