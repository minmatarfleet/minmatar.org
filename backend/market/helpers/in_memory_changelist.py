"""Shared ChangeList-compatible helpers for in-memory admin tables."""

from django.contrib.admin.views.main import (
    IGNORED_PARAMS,
    ORDER_VAR,
    PAGE_VAR,
    SEARCH_VAR,
    ChangeListSearchForm,
)
from django.core.exceptions import FieldDoesNotExist
from django.core.paginator import EmptyPage, InvalidPage, Paginator
from django.urls import NoReverseMatch
from django.utils.http import urlencode


def get_ordering_field(field_name, model_admin, model):
    try:
        field = model._meta.get_field(field_name)
        return field.name
    except FieldDoesNotExist:
        if hasattr(model_admin, field_name):
            attr = getattr(model_admin, field_name)
        else:
            return None
        if isinstance(attr, property) and hasattr(attr, "fget"):
            attr = attr.fget
        return getattr(attr, "admin_order_field", None)


def sort_rows(rows, list_display, model_admin, model, params):
    if ORDER_VAR not in params:
        return rows

    ordering = []
    for part in params[ORDER_VAR].split("."):
        _, prefix, index_text = part.rpartition("-")
        try:
            column_index = int(index_text)
        except ValueError:
            continue
        if column_index < 0 or column_index >= len(list_display):
            continue
        order_field = get_ordering_field(
            list_display[column_index], model_admin, model
        )
        if order_field:
            ordering.append((order_field, prefix == "-"))

    if not ordering:
        return rows

    def sort_key(row):
        parts = []
        for field, descending in ordering:
            value = row.get(field)
            if value is None:
                parts.append((1, 0))
            else:
                parts.append((0, -value if descending else value))
        return parts

    return sorted(rows, key=sort_key)


class InMemoryAdminChangeList:
    """ChangeList-compatible helper for in-memory admin rows."""

    search_form_class = ChangeListSearchForm

    def __init__(
        self,
        request,
        *,
        model_admin,
        filtered_rows: list[dict],
        total_row_count: int,
        list_item_class,
        sort_rows_fn=sort_rows,
    ):
        self.request = request
        self.model_admin = model_admin
        self.model = model_admin.model
        self.opts = self.model._meta
        self.lookup_opts = self.opts
        self.search_fields = model_admin.get_search_fields(request)
        self.search_help_text = model_admin.search_help_text
        self.list_per_page = model_admin.list_per_page
        self.show_full_result_count = model_admin.show_full_result_count
        self.list_display = list(model_admin.get_list_display(request))
        self.list_display_links = model_admin.get_list_display_links(
            request, self.list_display
        )
        self.list_editable = ()
        self.sortable_by = None
        self.preserved_filters = model_admin.get_preserved_filters(request)
        self.formset = None
        self.show_all = False
        self.can_show_all = False
        self.is_popup = False
        self.add_facets = False
        self.is_facets_optional = False
        self.to_field = None

        search_form = self.search_form_class(request.GET)
        if search_form.is_valid():
            self.query = search_form.cleaned_data.get(SEARCH_VAR) or ""
        else:
            self.query = (request.GET.get(SEARCH_VAR) or "").strip()

        try:
            self.page_num = max(1, int(request.GET.get(PAGE_VAR, 1)))
        except (TypeError, ValueError):
            self.page_num = 1

        self.params = dict(request.GET.items())
        self.filter_params = dict(request.GET.lists())
        if PAGE_VAR in self.params:
            del self.params[PAGE_VAR]
            del self.filter_params[PAGE_VAR]

        (
            self.filter_specs,
            self.has_filters,
            remaining_lookup_params,
            _,
            self.has_active_filters,
        ) = self._get_filters(request)
        self.clear_all_filters_qs = self.get_query_string(
            new_params=dict(remaining_lookup_params.items()),
            remove=list(self.get_filters_params().keys()),
        )

        sorted_rows = sort_rows_fn(
            filtered_rows,
            self.list_display,
            model_admin,
            self.model,
            self.params,
        )
        self.full_result_count = total_row_count
        self.result_count = len(sorted_rows)
        paginator = Paginator(sorted_rows, self.list_per_page)
        self.paginator = paginator
        try:
            page = paginator.page(self.page_num)
        except (EmptyPage, InvalidPage):
            page = paginator.page(1)
            self.page_num = 1
        self.result_list = [list_item_class(row) for row in page.object_list]
        self.multi_page = paginator.num_pages > 1

    def get_ordering_field(self, field_name):
        return get_ordering_field(field_name, self.model_admin, self.model)

    def get_ordering_field_columns(self):
        ordering_fields = {}
        if ORDER_VAR not in self.params:
            return ordering_fields
        for part in self.params[ORDER_VAR].split("."):
            _, prefix, index_text = part.rpartition("-")
            try:
                column_index = int(index_text)
            except ValueError:
                continue
            ordering_fields[column_index] = "desc" if prefix == "-" else "asc"
        return ordering_fields

    def get_filters_params(self, params=None):
        params = params or self.filter_params
        lookup_params = params.copy()
        for ignored in IGNORED_PARAMS:
            lookup_params.pop(ignored, None)
        return lookup_params

    def _get_filters(self, request):
        lookup_params = self.get_filters_params()
        has_active_filters = False
        filter_specs = []

        for list_filter in self.model_admin.list_filter:
            lookup_params_count = len(lookup_params)
            spec = list_filter(
                request, lookup_params, self.model, self.model_admin
            )
            if spec and spec.has_output():
                filter_specs.append(spec)
                if lookup_params_count > len(lookup_params):
                    has_active_filters = True

        return (
            filter_specs,
            bool(filter_specs),
            lookup_params,
            False,
            has_active_filters,
        )

    def get_query_string(self, new_params=None, remove=None):
        if new_params is None:
            new_params = {}
        if remove is None:
            remove = []
        params = self.filter_params.copy()
        for prefix in remove:
            for key in list(params):
                if key == prefix or key.startswith(f"{prefix}__"):
                    del params[key]
        for key, value in new_params.items():
            if value is None:
                params.pop(key, None)
            else:
                params[key] = value
        encoded = urlencode(sorted(params.items()), doseq=True)
        return f"?{encoded}" if encoded else "?"

    def url_for_result(self, result):
        raise NoReverseMatch()
