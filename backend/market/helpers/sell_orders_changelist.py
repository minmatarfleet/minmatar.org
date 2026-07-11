"""Django admin changelist components for the location sell-orders view."""

from django.contrib import admin
from django.contrib.admin.exceptions import DisallowedModelAdminLookup
from django.contrib.humanize.templatetags.humanize import intcomma, naturaltime
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from eveuniverse.models import EveType

from market.helpers.in_memory_changelist import (
    InMemoryAdminChangeList,
    sort_rows as _sort_sell_order_rows,
)

SELL_ORDER_PAGE_SIZE = 50

PINNED_ITEM_ICON = mark_safe(
    '<svg class="pinned-icon" viewBox="0 0 16 16" width="14" height="14" '
    'aria-hidden="true" focusable="false">'
    '<path fill="currentColor" d="M9.5 2.5 8 1 6.5 2.5V7L4 9.5V11h8V9.5L9.5 7V2.5zM7 13.5h2V15H7v-1.5z"/>'
    "</svg>"
)


class SellOrderListItem:
    """Row object for Django admin list_display rendering."""

    _meta = EveType._meta

    def __init__(self, row: dict):
        self.item_name = row["item_name"]
        self.type_id = row.get("type_id")
        self.current_qty = row["current_qty"]
        self.desired_qty = row["desired_qty"]
        self.recommended_qty = row["recommended_qty"]
        self.list_price = row.get("list_price")
        self.jita_sell_price = row.get("jita_sell_price")
        self.markup_pct = row.get("markup_pct")
        self.volume_90d = row.get("volume_90d")
        self.references_display = row.get("references_display", "")
        self.references_tooltip = row.get("references_tooltip", "")
        self.references_names = row.get("references_names", [])
        self.sources = row.get("sources", "")
        self.is_pinned = row.get("is_pinned", False)
        self.is_editable = row.get("is_editable", False)
        self.last_synced_at = row.get("last_synced_at")
        self.pk = (
            self.type_id
            if self.type_id is not None
            else -(abs(hash(self.item_name)) % (10**9))
        )
        self.id = self.pk

    def serializable_value(self, field_name):
        return getattr(self, field_name, self.pk)


class SellOrderSourceListFilter(admin.SimpleListFilter):
    title = _("where need comes from")
    parameter_name = "source"

    def lookups(self, request, model_admin):
        return (
            ("refit", _("Fleet ship — extra modules")),
            ("consumable", _("Fleet ship — ammo & charges")),
            ("non-doctrine ship", _("Market ship fit")),
        )

    def queryset(self, request, queryset):
        return queryset


class SellOrderStockListFilter(admin.SimpleListFilter):
    title = _("stock level")
    parameter_name = "stock"

    def lookups(self, request, model_admin):
        return (
            ("no_stock", _("Nothing listed")),
            ("very_understocked", _("Far below target")),
            ("understocked", _("Below target")),
            ("overstocked", _("Above target")),
            ("very_overstocked", _("Far above target")),
        )

    def queryset(self, request, queryset):
        return queryset


class SellOrderMarkupListFilter(admin.SimpleListFilter):
    title = _("price vs Jita")
    parameter_name = "markup"

    def lookups(self, request, model_admin):
        return (
            ("very_underpriced", _("Much cheaper than Jita")),
            ("underpriced", _("Cheaper than Jita")),
            ("normal", _("Near Jita price")),
            ("overpriced", _("More expensive than Jita")),
            ("very_overpriced", _("Much more expensive than Jita")),
        )

    def queryset(self, request, queryset):
        return queryset


class LocationSellOrdersModelAdmin(admin.ModelAdmin):
    """ModelAdmin used only for changelist display helpers (not registered)."""

    list_per_page = SELL_ORDER_PAGE_SIZE
    search_fields = ("item_name",)
    search_help_text = _("Search by item name or ship fit name.")
    list_filter = (
        SellOrderSourceListFilter,
        SellOrderStockListFilter,
        SellOrderMarkupListFilter,
    )
    list_display = (
        "display_item_name",
        "display_current_qty",
        "display_last_synced",
        "display_desired_qty",
        "display_recommended_qty",
        "display_list_price",
        "display_jita_sell_price",
        "display_markup_pct",
        "display_volume_90d",
        "display_references",
    )
    list_display_links = None
    show_full_result_count = True

    @admin.display(description=_("Item"))
    def display_item_name(self, obj: SellOrderListItem):
        if not obj.is_pinned:
            return obj.item_name
        return format_html(
            '<span class="item-name-with-pin">'
            '<span class="pinned-hover">'
            "{}"
            '<span class="pinned-tooltip">{}</span>'
            "</span>"
            '<span class="item-name-text">{}</span>'
            "</span>",
            PINNED_ITEM_ICON,
            _("You set the target stock for this item manually."),
            obj.item_name,
        )

    @admin.display(description=_("Listed now"), ordering="current_qty")
    def display_current_qty(self, obj: SellOrderListItem):
        return obj.current_qty

    @admin.display(description=_("Last synced"), ordering="last_synced_at")
    def display_last_synced(self, obj: SellOrderListItem):
        if obj.last_synced_at is None:
            return "—"
        return format_html(
            '<span title="{}">{}</span>',
            obj.last_synced_at.strftime("%Y-%m-%d %H:%M"),
            naturaltime(obj.last_synced_at),
        )

    @admin.display(description=_("Target stock"))
    def display_desired_qty(self, obj: SellOrderListItem):
        if obj.is_editable:
            return format_html(
                '<input type="number" name="desired_{}" value="{}" min="0" step="1" class="vIntegerField">',
                obj.type_id,
                obj.desired_qty,
            )
        return obj.desired_qty

    @admin.display(description=_("Suggested stock"))
    def display_recommended_qty(self, obj: SellOrderListItem):
        if not obj.recommended_qty:
            return obj.recommended_qty
        return format_html(
            '<span class="references-hover">'
            '<span class="references-count">{}</span>'
            '<span class="references-tooltip">{}</span>'
            "</span>",
            obj.recommended_qty,
            _(
                "Ammo, charges, and refit modules for doctrine fittings for sale, "
                "multiplied by how many of each ship you configured."
            ),
        )

    @admin.display(description=_("Lowest sell price"))
    def display_list_price(self, obj: SellOrderListItem):
        if obj.list_price is None:
            return "—"
        return intcomma(obj.list_price)

    @admin.display(description=_("Jita sell price"))
    def display_jita_sell_price(self, obj: SellOrderListItem):
        if obj.jita_sell_price is None:
            return "—"
        return intcomma(obj.jita_sell_price)

    @admin.display(description=_("vs Jita %"), ordering="markup_pct")
    def display_markup_pct(self, obj: SellOrderListItem):
        if obj.markup_pct is None:
            return "—"
        return f"{obj.markup_pct}%"

    @admin.display(
        description=_("Jita sales (90 days)"), ordering="volume_90d"
    )
    def display_volume_90d(self, obj: SellOrderListItem):
        if obj.volume_90d is None:
            return "—"
        return intcomma(obj.volume_90d)

    @admin.display(description=_("Needed for"))
    def display_references(self, obj: SellOrderListItem):
        if not obj.references_names:
            return "—"
        return format_html(
            '<span class="references-hover">'
            '<span class="references-count">{}</span>'
            '<span class="references-tooltip">{}</span>'
            "</span>",
            obj.references_display,
            obj.references_tooltip,
        )

    def get_queryset(self, request):
        return EveType.objects.none()

    def lookup_allowed(self, lookup, value, request=None):
        if lookup in {
            SellOrderSourceListFilter.parameter_name,
            SellOrderStockListFilter.parameter_name,
            SellOrderMarkupListFilter.parameter_name,
        }:
            return True
        raise DisallowedModelAdminLookup(f"Filtering by {lookup} not allowed")

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LocationSellOrdersChangeList(InMemoryAdminChangeList):
    """ChangeList-compatible helper for in-memory sell-order rows."""

    def __init__(
        self, request, *, model_admin, filtered_rows, total_row_count
    ):
        super().__init__(
            request,
            model_admin=model_admin,
            filtered_rows=filtered_rows,
            total_row_count=total_row_count,
            list_item_class=SellOrderListItem,
            sort_rows_fn=_sort_sell_order_rows,
        )
