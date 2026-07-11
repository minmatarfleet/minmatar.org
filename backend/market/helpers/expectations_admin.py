from django.contrib import admin
from django.contrib.admin.views.main import PAGE_VAR, SEARCH_VAR
from django.db.models import Count
from django.urls import reverse
from django.utils.http import urlencode

from fittings.models import EveDoctrineFitting

from market.helpers.contract_admin import count_mismatched_contracts
from market.helpers.expectations_changelist import (
    _format_doctrine_display,
    build_contract_expectations_changelist,
    build_fitting_expectations_changelist,
)
from market.helpers.qualification import (
    get_all_doctrine_fittings,
    get_doctrine_names_by_fitting_id,
    get_non_doctrine_fittings,
)
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketFittingExpectation,
)
from market.models.item import parse_eft_items


def filter_fitting_expectation_rows(
    rows: list[dict],
    *,
    search: str = "",
    tag_filter: str = "",
    configured_filter: str = "",
) -> list[dict]:
    filtered = rows
    if search:
        needle = search.casefold()
        filtered = [
            row for row in filtered if needle in row["fitting_name"].casefold()
        ]
    if tag_filter:
        filtered = [
            row
            for row in filtered
            if tag_filter in row.get("fitting_tags", [])
        ]
    if configured_filter == "yes":
        filtered = [
            row for row in filtered if row.get("quantity") not in (None, 0)
        ]
    elif configured_filter == "no":
        filtered = [
            row for row in filtered if row.get("quantity") in (None, 0)
        ]
    return filtered


def _doctrine_filters_from_request(request) -> list[str]:
    if request is None:
        return []
    return [
        value.strip()
        for value in request.GET.getlist("doctrine")
        if value.strip()
    ]


def filter_contract_expectation_rows(
    rows: list[dict],
    *,
    search: str = "",
    doctrine_filters: list[str] | None = None,
) -> list[dict]:
    filtered = rows
    if search:
        needle = search.casefold()
        filtered = [
            row
            for row in filtered
            if needle in row["fitting_name"].casefold()
            or needle in row.get("doctrine_names", "").casefold()
        ]
    if doctrine_filters:
        doctrine_ids = {int(value) for value in doctrine_filters}
        filtered = [
            row
            for row in filtered
            if doctrine_ids.intersection(row.get("doctrine_ids", []))
        ]
    return filtered


def _save_fitting_quantity_expectations(
    location,
    post_data,
    model_class,
    *,
    prefix: str = "quantity_",
    allowed_ids: set[int] | None = None,
) -> int:
    updated = 0
    for key, raw_value in post_data.items():
        if not key.startswith(prefix):
            continue
        fitting_id = int(key.removeprefix(prefix))
        if allowed_ids is not None and fitting_id not in allowed_ids:
            continue
        if raw_value in (None, ""):
            deleted, _ = model_class.objects.filter(
                location=location,
                fitting_id=fitting_id,
            ).delete()
            if deleted:
                updated += 1
            continue
        quantity = int(raw_value)
        if quantity <= 0:
            deleted, _ = model_class.objects.filter(
                location=location,
                fitting_id=fitting_id,
            ).delete()
            if deleted:
                updated += 1
            continue
        model_class.objects.update_or_create(
            location=location,
            fitting_id=fitting_id,
            defaults={"quantity": quantity},
        )
        updated += 1
    return updated


def save_fitting_expectation_quantities(
    location, post_data, allowed_ids: set[int] | None = None
) -> int:
    return _save_fitting_quantity_expectations(
        location,
        post_data,
        EveMarketFittingExpectation,
        allowed_ids=allowed_ids,
    )


def save_contract_expectation_quantities(
    location, post_data, allowed_ids: set[int] | None = None
) -> int:
    return _save_fitting_quantity_expectations(
        location,
        post_data,
        EveMarketContractExpectation,
        allowed_ids=allowed_ids,
    )


def build_fitting_expectation_rows(location) -> list[dict]:
    qualified_fittings = list(get_non_doctrine_fittings())
    expectations = {
        row.fitting_id: row
        for row in EveMarketFittingExpectation.objects.filter(
            location=location
        ).select_related("fitting")
    }

    rows = []
    for fitting in qualified_fittings:
        expectation = expectations.get(fitting.pk)
        rows.append(
            {
                "fitting_id": fitting.pk,
                "fitting_name": fitting.name,
                "fitting_tags": fitting.tags or [],
                "quantity": expectation.quantity if expectation else None,
                "item_count": len(parse_eft_items(fitting.eft_format)),
            }
        )
    return rows


def build_contract_expectation_rows(location) -> list[dict]:
    qualified_fittings = list(get_all_doctrine_fittings())
    fitting_ids = [fitting.pk for fitting in qualified_fittings]
    doctrine_names_by_fitting = get_doctrine_names_by_fitting_id(fitting_ids)
    doctrine_ids_by_fitting: dict[int, list[int]] = {}
    if fitting_ids:
        for fitting_id, doctrine_id in EveDoctrineFitting.objects.filter(
            fitting_id__in=fitting_ids
        ).values_list("fitting_id", "doctrine_id"):
            doctrine_ids_by_fitting.setdefault(fitting_id, []).append(
                doctrine_id
            )

    expectations = {
        row.fitting_id: row
        for row in EveMarketContractExpectation.objects.filter(
            location=location
        ).select_related("fitting")
    }
    outstanding_by_fitting = {
        row["fitting_id"]: row["c"]
        for row in EveMarketContract.objects.filter(
            location=location,
            status="outstanding",
            fitting__isnull=False,
        )
        .values("fitting_id")
        .annotate(c=Count("id"))
    }
    sold_by_fitting = {
        row["fitting_id"]: row["c"]
        for row in EveMarketContract.objects.filter(
            location=location, status="finished", fitting__isnull=False
        )
        .values("fitting_id")
        .annotate(c=Count("id"))
    }

    rows = []
    for fitting in qualified_fittings:
        expectation = expectations.get(fitting.pk)
        doctrine_names = doctrine_names_by_fitting.get(fitting.pk, [])
        doctrines_display, doctrines_tooltip, doctrines_names = (
            _format_doctrine_display(doctrine_names)
        )
        rows.append(
            {
                "fitting_id": fitting.pk,
                "fitting_name": fitting.name,
                "fitting_tags": fitting.tags or [],
                "doctrine_names": ", ".join(doctrine_names),
                "doctrine_names_list": doctrines_names,
                "doctrines_display": doctrines_display,
                "doctrines_tooltip": doctrines_tooltip,
                "doctrine_ids": doctrine_ids_by_fitting.get(fitting.pk, []),
                "quantity": expectation.quantity if expectation else None,
                "current": outstanding_by_fitting.get(fitting.pk, 0),
                "sold": sold_by_fitting.get(fitting.pk, 0),
            }
        )
    return rows


def _fitting_expectation_query_params(
    request, *, page: int | None = None
) -> dict:
    params = {}
    if request is None:
        return params
    search = (request.GET.get(SEARCH_VAR) or "").strip()
    if search:
        params[SEARCH_VAR] = search
    tag_filter = (request.GET.get("tag") or "").strip()
    if tag_filter:
        params["tag"] = tag_filter
    configured_filter = (request.GET.get("configured") or "").strip()
    if configured_filter:
        params["configured"] = configured_filter
    if page and page > 1:
        params[PAGE_VAR] = str(page)
    return params


def _expectation_query_params(
    request, *, page: int | None = None
) -> dict[str, str]:
    params = {}
    if request is None:
        return params
    search = (request.GET.get(SEARCH_VAR) or "").strip()
    if search:
        params[SEARCH_VAR] = search
    doctrine_filters = _doctrine_filters_from_request(request)
    if doctrine_filters:
        params["doctrine"] = doctrine_filters
    if page and page > 1:
        params[PAGE_VAR] = str(page)
    return params


def build_location_fitting_expectations_context(
    location, request=None
) -> dict:
    all_rows = build_fitting_expectation_rows(location)
    search = ""
    tag_filter = ""
    configured_filter = ""
    if request is not None:
        search = (request.GET.get(SEARCH_VAR) or "").strip()
        tag_filter = (request.GET.get("tag") or "").strip()
        configured_filter = (request.GET.get("configured") or "").strip()
    filtered_rows = filter_fitting_expectation_rows(
        all_rows,
        search=search,
        tag_filter=tag_filter,
        configured_filter=configured_filter,
    )
    model_admin = None
    cl = None
    if request is not None:
        cl = build_fitting_expectations_changelist(
            request,
            filtered_rows=filtered_rows,
            total_row_count=len(all_rows),
        )
        model_admin = cl.model_admin

    base_params = _fitting_expectation_query_params(request)
    form_action = reverse(
        "admin:market_location_fitting_expectations",
        args=[location.pk],
    )
    form_action_query = urlencode(base_params, doseq=True)
    if form_action_query:
        form_action = f"{form_action}?{form_action_query}"

    opts = (
        model_admin.model._meta
        if model_admin is not None
        else EveMarketFittingExpectation._meta
    )

    return {
        "cl": cl,
        "opts": opts,
        "media": (
            model_admin.media
            if model_admin is not None
            else admin.ModelAdmin(
                EveMarketFittingExpectation, admin.site
            ).media
        ),
        "form_action": form_action,
        "total_row_count": len(all_rows),
        "filtered_row_count": len(filtered_rows),
        "help_text": (
            f"Showing {len(filtered_rows)} of {len(all_rows)} non-doctrine ship fits."
        ),
        "save_button_label": "Save quantities",
        "page_title": "Non-doctrine fittings for sale",
        "page_intro": (
            "Set how many of each non-doctrine ship fit you want stocked at this location."
        ),
        "page_help_bullets": [
            (
                "How many to stock",
                "Complete ship fits you want listed on the market.",
            ),
            (
                "Shared modules",
                "If several fits use the same module, the market status page uses "
                "the highest quantity needed — not the sum — so one listing can "
                "cover multiple fits.",
            ),
            (
                "Items in fit",
                "Number of unique items in that fit, including the hull.",
            ),
        ],
    }


def build_location_contract_expectations_context(
    location, request=None
) -> dict:
    all_rows = build_contract_expectation_rows(location)
    search = ""
    doctrine_filters: list[str] = []
    if request is not None:
        search = (request.GET.get(SEARCH_VAR) or "").strip()
        doctrine_filters = _doctrine_filters_from_request(request)
    filtered_rows = filter_contract_expectation_rows(
        all_rows,
        search=search,
        doctrine_filters=doctrine_filters,
    )
    model_admin = None
    cl = None
    if request is not None:
        cl = build_contract_expectations_changelist(
            request,
            filtered_rows=filtered_rows,
            total_row_count=len(all_rows),
        )
        model_admin = cl.model_admin

    base_params = _expectation_query_params(request)
    form_action = reverse(
        "admin:market_location_contract_expectations",
        args=[location.pk],
    )
    form_action_query = urlencode(base_params, doseq=True)
    if form_action_query:
        form_action = f"{form_action}?{form_action_query}"

    opts = (
        model_admin.model._meta
        if model_admin is not None
        else EveMarketContractExpectation._meta
    )

    return {
        "cl": cl,
        "opts": opts,
        "media": (
            model_admin.media
            if model_admin is not None
            else admin.ModelAdmin(
                EveMarketContractExpectation, admin.site
            ).media
        ),
        "form_action": form_action,
        "total_row_count": len(all_rows),
        "filtered_row_count": len(filtered_rows),
        "help_text": (
            f"Showing {len(filtered_rows)} of {len(all_rows)} fleet ship fits."
        ),
        "save_button_label": "Save quantities",
        "page_title": "Doctrine fittings for sale",
        "page_intro": (
            "Configure how many of each doctrine ship should be offered — this page "
            "is per ship fit, not individual contract listings. "
            "Suggested stock on the market status page is calculated from these quantities."
        ),
        "mismatched_contracts_url": reverse(
            "admin:market_location_contracts",
            args=[location.pk],
        ),
        "mismatched_contract_count": count_mismatched_contracts(location),
    }
