"""Django admin changelist components for fitting/contract expectation views."""

from django.contrib import admin
from django.contrib.admin.exceptions import DisallowedModelAdminLookup
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from fittings.models import EveDoctrine, FittingTag

from market.helpers.in_memory_changelist import (
    InMemoryAdminChangeList,
    sort_rows as _sort_expectation_rows,
)

from market.models import (
    EveMarketContractExpectation,
    EveMarketFittingExpectation,
)

EXPECTATION_PAGE_SIZE = 15
# The non-doctrine fitting list tops out at a few hundred rows, so render it
# unpaginated: paginating splits the save form across pages and only the
# visible page gets saved.
FITTING_EXPECTATION_PAGE_SIZE = 10_000


class FittingExpectationListItem:
    _meta = EveMarketFittingExpectation._meta

    def __init__(self, row: dict):
        self.fitting_id = row["fitting_id"]
        self.fitting_name = row["fitting_name"]
        self.quantity = row.get("quantity")
        self.item_count = row["item_count"]
        self.pk = self.fitting_id
        self.id = self.fitting_id

    def serializable_value(self, field_name):
        return getattr(self, field_name, self.pk)


class ContractExpectationListItem:
    _meta = EveMarketContractExpectation._meta

    def __init__(self, row: dict):
        self.fitting_id = row["fitting_id"]
        self.fitting_name = row["fitting_name"]
        self.doctrine_names_list = row.get("doctrine_names_list", [])
        self.doctrines_display = row.get("doctrines_display", "")
        self.doctrines_tooltip = row.get("doctrines_tooltip", "")
        self.quantity = row.get("quantity")
        self.current = row.get("current", 0)
        self.sold = row.get("sold", 0)
        self.pk = self.fitting_id
        self.id = self.fitting_id

    def serializable_value(self, field_name):
        return getattr(self, field_name, self.pk)


class FittingTagListFilter(admin.SimpleListFilter):
    title = _("ship type tag")
    parameter_name = "tag"

    def lookups(self, request, model_admin):
        return FittingTag.choices

    def queryset(self, request, queryset):
        return queryset


class FittingConfiguredListFilter(admin.SimpleListFilter):
    title = _("configuration")
    parameter_name = "configured"

    def lookups(self, request, model_admin):
        return (
            ("yes", _("Quantity set")),
            ("no", _("Not configured yet")),
        )

    def queryset(self, request, queryset):
        return queryset


class ContractDoctrineListFilter(admin.ListFilter):
    title = _("fleet doctrine")
    parameter_name = "doctrine"

    def __init__(self, request, params, model, model_admin):
        super().__init__(request, params, model, model_admin)
        values = params.pop(self.parameter_name, None)
        if values:
            self.used_parameters[self.parameter_name] = values
        self.selected_values = self._parse_selected_values()
        lookup_choices = self.lookups(request, model_admin)
        self.lookup_choices = list(lookup_choices or ())

    def has_output(self):
        return len(self.lookup_choices) > 0

    def _parse_selected_values(self) -> set[int]:
        raw = self.used_parameters.get(self.parameter_name, [])
        if isinstance(raw, str):
            raw = [raw]
        selected: set[int] = set()
        for value in raw:
            try:
                selected.add(int(value))
            except (TypeError, ValueError):
                continue
        return selected

    def expected_parameters(self):
        return [self.parameter_name]

    def lookups(self, request, model_admin):
        return list(
            EveDoctrine.objects.order_by("name").values_list("pk", "name")
        )

    def queryset(self, request, queryset):
        return queryset

    def choices(self, changelist):
        selected = self.selected_values
        yield {
            "selected": not selected,
            "query_string": changelist.get_query_string(
                remove=[self.parameter_name]
            ),
            "display": _("All"),
        }
        for lookup, title in self.lookup_choices:
            doctrine_id = int(lookup)
            if doctrine_id in selected:
                remaining = sorted(selected - {doctrine_id})
                if remaining:
                    query_string = changelist.get_query_string(
                        {
                            self.parameter_name: [
                                str(value) for value in remaining
                            ]
                        }
                    )
                else:
                    query_string = changelist.get_query_string(
                        remove=[self.parameter_name]
                    )
                is_selected = True
            else:
                query_string = changelist.get_query_string(
                    {
                        self.parameter_name: [
                            str(value)
                            for value in sorted(selected | {doctrine_id})
                        ]
                    }
                )
                is_selected = False
            yield {
                "selected": is_selected,
                "query_string": query_string,
                "display": title,
            }


def _format_doctrine_display(
    doctrine_names: list[str],
) -> tuple[str, str, list[str]]:
    if not doctrine_names:
        return "", "", []
    count = len(doctrine_names)
    return f"{count} doctrines", "\n".join(doctrine_names), doctrine_names


def _quantity_input(fitting_id: int, quantity: int | None) -> str:
    value = "" if quantity is None else quantity
    return format_html(
        '<input type="number" name="quantity_{}" value="{}" min="0" step="1" class="vIntegerField">',
        fitting_id,
        value,
    )


class LocationFittingExpectationsModelAdmin(admin.ModelAdmin):
    list_per_page = FITTING_EXPECTATION_PAGE_SIZE
    search_fields = ("fitting_name",)
    search_help_text = _("Search by ship fit name.")
    list_filter = (FittingTagListFilter, FittingConfiguredListFilter)
    list_display = (
        "display_fitting_name",
        "display_quantity",
        "display_item_count",
    )
    list_display_links = None
    show_full_result_count = True

    @admin.display(description=_("Ship fit"), ordering="fitting_name")
    def display_fitting_name(self, obj: FittingExpectationListItem):
        return obj.fitting_name

    @admin.display(description=_("How many to stock"), ordering="quantity")
    def display_quantity(self, obj: FittingExpectationListItem):
        return _quantity_input(obj.fitting_id, obj.quantity)

    @admin.display(description=_("Items in fit"), ordering="item_count")
    def display_item_count(self, obj: FittingExpectationListItem):
        return obj.item_count

    def get_queryset(self, request):
        return EveMarketFittingExpectation.objects.none()

    def lookup_allowed(self, lookup, value, request=None):
        if lookup in {
            FittingTagListFilter.parameter_name,
            FittingConfiguredListFilter.parameter_name,
        }:
            return True
        raise DisallowedModelAdminLookup(f"Filtering by {lookup} not allowed")

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LocationContractExpectationsModelAdmin(admin.ModelAdmin):
    list_per_page = EXPECTATION_PAGE_SIZE
    search_fields = ("fitting_name", "doctrine_names")
    search_help_text = _("Search by ship fit or doctrine name.")
    list_filter = (ContractDoctrineListFilter,)
    list_display = (
        "display_fitting_name",
        "display_current",
        "display_quantity",
        "display_sold",
        "display_doctrines",
    )
    list_display_links = None
    show_full_result_count = True

    @admin.display(description=_("Ship fit"), ordering="fitting_name")
    def display_fitting_name(self, obj: ContractExpectationListItem):
        return obj.fitting_name

    @admin.display(description=_("Outstanding (count)"), ordering="current")
    def display_current(self, obj: ContractExpectationListItem):
        return obj.current

    @admin.display(description=_("How many to offer"), ordering="quantity")
    def display_quantity(self, obj: ContractExpectationListItem):
        return _quantity_input(obj.fitting_id, obj.quantity)

    @admin.display(description=_("Completed sales"), ordering="sold")
    def display_sold(self, obj: ContractExpectationListItem):
        return obj.sold

    @admin.display(description=_("Fleet doctrines"))
    def display_doctrines(self, obj: ContractExpectationListItem):
        if not obj.doctrine_names_list:
            return "—"
        return format_html(
            '<span class="doctrines-hover">'
            '<span class="doctrines-count">{}</span>'
            '<span class="doctrines-tooltip">{}</span>'
            "</span>",
            obj.doctrines_display,
            obj.doctrines_tooltip,
        )

    def get_queryset(self, request):
        return EveMarketContractExpectation.objects.none()

    def lookup_allowed(self, lookup, value, request=None):
        if lookup == ContractDoctrineListFilter.parameter_name:
            return True
        raise DisallowedModelAdminLookup(f"Filtering by {lookup} not allowed")

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class InMemoryExpectationsChangeList(InMemoryAdminChangeList):
    """ChangeList-compatible helper for in-memory expectation rows."""

    def __init__(
        self,
        request,
        *,
        model_admin,
        filtered_rows,
        total_row_count,
        list_item_class,
    ):
        super().__init__(
            request,
            model_admin=model_admin,
            filtered_rows=filtered_rows,
            total_row_count=total_row_count,
            list_item_class=list_item_class,
            sort_rows_fn=_sort_expectation_rows,
        )


def build_fitting_expectations_changelist(
    request, *, filtered_rows: list[dict], total_row_count: int
):
    model_admin = LocationFittingExpectationsModelAdmin(
        EveMarketFittingExpectation, admin.site
    )
    return InMemoryExpectationsChangeList(
        request,
        model_admin=model_admin,
        filtered_rows=filtered_rows,
        total_row_count=total_row_count,
        list_item_class=FittingExpectationListItem,
    )


def build_contract_expectations_changelist(
    request, *, filtered_rows: list[dict], total_row_count: int
):
    model_admin = LocationContractExpectationsModelAdmin(
        EveMarketContractExpectation, admin.site
    )
    return InMemoryExpectationsChangeList(
        request,
        model_admin=model_admin,
        filtered_rows=filtered_rows,
        total_row_count=total_row_count,
        list_item_class=ContractExpectationListItem,
    )
