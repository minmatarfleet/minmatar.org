"""Custom market location admin views."""

from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import reverse

from eveonline.models import EveLocation

from market.helpers.admin_views import (
    get_location_or_redirect,
    handle_location_post,
    render_location_view,
)
from market.helpers.buy_orders import build_location_buy_orders_context
from market.helpers.contract_admin import build_location_contracts_context
from market.helpers.expectations_admin import (
    build_location_contract_expectations_context,
    build_location_fitting_expectations_context,
    save_contract_expectation_quantities,
    save_fitting_expectation_quantities,
)
from market.helpers.permissions import (
    CHANGE_CONTRACT_EXPECTATIONS,
    CHANGE_FITTING_EXPECTATIONS,
    CHANGE_ITEM_EXPECTATIONS,
    VIEW_BUY_ORDER_EXPECTATIONS,
    VIEW_CONTRACT_EXPECTATIONS,
    VIEW_FITTING_EXPECTATIONS,
    VIEW_ITEM_EXPECTATIONS,
    VIEW_MARKET_CONTRACTS,
    VIEW_MARKET_LOCATIONS,
    require_view_perm,
)
from market.helpers.sell_orders import (
    build_location_sell_orders_context,
    save_sell_order_desired_quantities,
)
from market.models.item import _get_consumable_items
from market.models import (
    EveMarketContractExpectation,
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
)


def _allowed_fitting_ids(context) -> set[int]:
    cl = context.get("cl")
    if cl is None:
        return set()
    return {item.fitting_id for item in cl.result_list}


def _allowed_type_ids(context) -> set[int]:
    cl = context.get("cl")
    if cl is None:
        return set()
    return {
        item.type_id for item in cl.result_list if item.type_id is not None
    }


def market_locations_view(request):
    require_view_perm(request.user, VIEW_MARKET_LOCATIONS)
    locations = EveLocation.objects.filter(market_active=True).order_by(
        "location_name"
    )
    rows = []
    for location in locations:
        rows.append(
            {
                "location": location,
                "hub_url": reverse(
                    "admin:market_location_hub", args=[location.pk]
                ),
                "categories": location.market_categories or [],
            }
        )
    context = {
        **admin.site.each_context(request),
        "title": "Market locations",
        "rows": rows,
    }
    return TemplateResponse(
        request, "admin/market/locations_list.html", context
    )


def market_location_hub_view(request, location_id):
    location, redirect = get_location_or_redirect(request, location_id)
    if redirect:
        return redirect
    return render_location_view(
        request,
        location=location,
        title=f"Market — {location.location_name}",
        template_name="admin/market/location_hub.html",
        context={},
        view_perm=VIEW_MARKET_LOCATIONS,
    )


def market_location_contracts_view(request, location_id):
    location, redirect = get_location_or_redirect(request, location_id)
    if redirect:
        return redirect
    return render_location_view(
        request,
        location=location,
        title=f"Mismatched contracts — {location.location_name}",
        template_name="admin/market/location_contracts.html",
        context=build_location_contracts_context(location),
        view_perm=VIEW_MARKET_CONTRACTS,
    )


def market_location_buy_orders_view(request, location_id):
    location, redirect = get_location_or_redirect(request, location_id)
    if redirect:
        return redirect
    return render_location_view(
        request,
        location=location,
        title=f"Configure buy orders — {location.location_name}",
        template_name="admin/market/location_buy_orders.html",
        context=build_location_buy_orders_context(location),
        view_perm=VIEW_BUY_ORDER_EXPECTATIONS,
    )


def market_location_fitting_expectations_view(request, location_id):
    location, redirect = get_location_or_redirect(request, location_id)
    if redirect:
        return redirect

    if request.method == "POST":
        page_context = build_location_fitting_expectations_context(
            location, request
        )
        return handle_location_post(
            request,
            location=location,
            url_name="admin:market_location_fitting_expectations",
            change_perm=CHANGE_FITTING_EXPECTATIONS,
            save_fn=save_fitting_expectation_quantities,
            success_message="Quantities saved.",
            allowed_ids=_allowed_fitting_ids(page_context),
        )

    return render_location_view(
        request,
        location=location,
        title=f"Non-doctrine fittings for sale — {location.location_name}",
        template_name="admin/market/location_fitting_expectations.html",
        context=build_location_fitting_expectations_context(location, request),
        view_perm=VIEW_FITTING_EXPECTATIONS,
    )


def market_location_contract_expectations_view(request, location_id):
    location, redirect = get_location_or_redirect(request, location_id)
    if redirect:
        return redirect

    if request.method == "POST":
        page_context = build_location_contract_expectations_context(
            location, request
        )
        return handle_location_post(
            request,
            location=location,
            url_name="admin:market_location_contract_expectations",
            change_perm=CHANGE_CONTRACT_EXPECTATIONS,
            save_fn=save_contract_expectation_quantities,
            success_message="Quantities saved.",
            allowed_ids=_allowed_fitting_ids(page_context),
        )

    return render_location_view(
        request,
        location=location,
        title=f"Doctrine fittings for sale — {location.location_name}",
        template_name="admin/market/location_contract_expectations.html",
        context=build_location_contract_expectations_context(
            location, request
        ),
        view_perm=VIEW_CONTRACT_EXPECTATIONS,
    )


def market_location_sell_orders_view(request, location_id):
    location, redirect = get_location_or_redirect(request, location_id)
    if redirect:
        return redirect

    if request.method == "POST":
        page_context = build_location_sell_orders_context(location, request)
        return handle_location_post(
            request,
            location=location,
            url_name="admin:market_location_sell_orders",
            change_perm=CHANGE_ITEM_EXPECTATIONS,
            save_fn=save_sell_order_desired_quantities,
            success_message="Target stock saved.",
            allowed_ids=_allowed_type_ids(page_context),
        )

    return render_location_view(
        request,
        location=location,
        title=f"View market status — {location.location_name}",
        template_name="admin/market/location_sell_orders.html",
        context=build_location_sell_orders_context(location, request),
        view_perm=VIEW_ITEM_EXPECTATIONS,
    )


def market_expectations_view(request):
    """Custom admin view listing all market expectations broken down to individual items."""
    require_view_perm(request.user, VIEW_ITEM_EXPECTATIONS)
    location_filter = request.GET.get("location")

    locations = EveLocation.objects.filter(market_active=True).order_by(
        "location_name"
    )

    item_qs = EveMarketItemExpectation.objects.select_related(
        "item", "location"
    )
    fitting_qs = EveMarketFittingExpectation.objects.select_related(
        "fitting", "location"
    )
    contract_qs = EveMarketContractExpectation.objects.select_related(
        "fitting", "location"
    )

    if location_filter:
        item_qs = item_qs.filter(location_id=location_filter)
        fitting_qs = fitting_qs.filter(location_id=location_filter)
        contract_qs = contract_qs.filter(location_id=location_filter)

    rows = []

    for exp in item_qs.order_by("item__name", "location__location_name"):
        rows.append(
            {
                "name": exp.item.name,
                "source": "Item",
                "location_name": exp.location.location_name,
                "quantity": exp.quantity,
                "edit_url": reverse(
                    "admin:market_evemarketitemexpectation_change",
                    args=[exp.pk],
                ),
            }
        )

    for exp in fitting_qs:
        edit_url = reverse(
            "admin:market_evemarketfittingexpectation_change",
            args=[exp.pk],
        )
        for item_name, qty in exp.get_item_quantities().items():
            rows.append(
                {
                    "name": item_name,
                    "source": f"Fitting: {exp.fitting.name}",
                    "location_name": exp.location.location_name,
                    "quantity": qty,
                    "edit_url": edit_url,
                }
            )

    for exp in contract_qs:
        edit_url = reverse(
            "admin:market_evemarketcontractexpectation_change",
            args=[exp.pk],
        )
        consumables = _get_consumable_items(exp.fitting)
        for item_name, qty in consumables.items():
            rows.append(
                {
                    "name": item_name,
                    "source": f"Doctrine: {exp.fitting.name}",
                    "location_name": exp.location.location_name,
                    "quantity": qty * exp.quantity,
                    "edit_url": edit_url,
                }
            )

    rows.sort(
        key=lambda r: (r["name"].lower(), r["source"], r["location_name"])
    )

    context = {
        **admin.site.each_context(request),
        "title": "Market expectations",
        "rows": rows,
        "locations": locations,
        "selected_location": location_filter or "",
        "add_item_url": reverse("admin:market_evemarketitemexpectation_add"),
        "add_fitting_url": reverse(
            "admin:market_evemarketfittingexpectation_add"
        ),
    }
    return TemplateResponse(
        request, "admin/market/expectations_list.html", context
    )
