"""Custom industry orders and loyalty admin views."""

from django.conf import settings
from django.db.models import Count
from django.urls import reverse

from industry.helpers.admin_urls import add_url, changelist_url
from industry.helpers.admin_views import (
    get_order_or_redirect,
    render_industry_orders_view,
    render_loyalty_admin_view,
)
from industry.helpers.order_profit_breakdown import (
    can_refresh_order_profit_breakdown,
)
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointContact,
    IndustryLoyaltyPointLedgerEntry,
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointPriceHistory,
    IndustryLpStoreOffer,
    IndustryOrder,
    IndustryOrderItemAssignment,
)


def _web_base() -> str:
    return getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org").rstrip(
        "/"
    )


def _order_counts(order: IndustryOrder) -> dict:
    item_count = order.items.count()
    assignment_count = IndustryOrderItemAssignment.objects.filter(
        order_item__order_id=order.pk
    ).count()
    return {"items": item_count, "assignments": assignment_count}


def industry_orders_home_view(request):
    orders = (
        IndustryOrder.objects.select_related("character", "location")
        .annotate(item_count=Count("items"))
        .order_by("-created_at")[:100]
    )
    order_rows = []
    for order in orders:
        counts = _order_counts(order)
        order_rows.append(
            {
                "order": order,
                "item_count": counts["items"],
                "assignment_count": counts["assignments"],
                "hub_url": reverse(
                    "admin:industry_order_hub", args=[order.pk]
                ),
                "edit_url": reverse(
                    "admin:industry_industryorder_change", args=[order.pk]
                ),
            }
        )
    return render_industry_orders_view(
        request,
        title="Industry orders",
        template_name="admin/industry/orders_home.html",
        context={
            "order_rows": order_rows,
            "add_order_url": reverse("admin:industry_industryorder_add"),
            "all_orders_url": changelist_url("industryorder"),
        },
    )


def industry_order_hub_view(request, order_id):
    order, redirect = get_order_or_redirect(request, order_id)
    if redirect:
        return redirect
    counts = _order_counts(order)
    order_filter = {"order__id__exact": order.pk}
    assignment_filter = {"order_item__order__id__exact": order.pk}
    return render_industry_orders_view(
        request,
        title=f"Industry order — #{order.pk}",
        template_name="admin/industry/order_hub.html",
        context={
            "order": order,
            "sections": {
                "settings": {
                    "edit_url": reverse(
                        "admin:industry_industryorder_change", args=[order.pk]
                    ),
                    "mark_fulfilled_url": reverse(
                        "admin:industry_industryorder_mark_fulfilled",
                        args=[order.pk],
                    ),
                    "refresh_profit_breakdown_url": reverse(
                        "admin:industry_industryorder_refresh_profit_breakdown",
                        args=[order.pk],
                    ),
                    "can_refresh_profit_breakdown": can_refresh_order_profit_breakdown(
                        order
                    ),
                    "profit_breakdown_computed_at": (
                        order.profit_breakdown_computed_at
                    ),
                },
                "items": {
                    "count": counts["items"],
                    "list_url": changelist_url(
                        "industryorderitem", **order_filter
                    ),
                    "add_url": add_url("industryorderitem", order=order.pk),
                },
                "assignments": {
                    "count": counts["assignments"],
                    "list_url": changelist_url(
                        "industryorderitemassignment",
                        **assignment_filter,
                    ),
                    "add_url": add_url("industryorderitemassignment"),
                },
            },
        },
    )


def industry_loyalty_home_view(request):
    """Hub linking currencies, accounts, ledger, market orders, and offers."""
    open_orders = IndustryLoyaltyPointMarketOrder.objects.filter(
        status=IndustryLoyaltyPointMarketOrder.Status.OPEN
    ).count()
    sections = {
        "currencies": {
            "count": IndustryLoyaltyPoint.objects.count(),
            "list_url": changelist_url("industryloyaltypoint"),
            "add_url": add_url("industryloyaltypoint"),
        },
        "accounts": {
            "count": IndustryLoyaltyPointAccount.objects.count(),
            "list_url": changelist_url("industryloyaltypointaccount"),
            "add_url": add_url("industryloyaltypointaccount"),
        },
        "contacts": {
            "count": IndustryLoyaltyPointContact.objects.count(),
            "list_url": changelist_url("industryloyaltypointcontact"),
            "add_url": add_url("industryloyaltypointcontact"),
        },
        "price_history": {
            "count": IndustryLoyaltyPointPriceHistory.objects.count(),
            "list_url": changelist_url("industryloyaltypointpricehistory"),
        },
        "ledger": {
            "count": IndustryLoyaltyPointLedgerEntry.objects.count(),
            "list_url": changelist_url("industryloyaltypointledgerentry"),
            "add_url": add_url("industryloyaltypointledgerentry"),
        },
        "market_orders": {
            "count": open_orders,
            "list_url": changelist_url("industryloyaltypointmarketorder"),
            "add_url": add_url("industryloyaltypointmarketorder"),
            "open_list_url": changelist_url(
                "industryloyaltypointmarketorder",
                status__exact=IndustryLoyaltyPointMarketOrder.Status.OPEN,
            ),
        },
        "store_offers": {
            "count": IndustryLpStoreOffer.objects.count(),
            "list_url": f"{_web_base()}/industry/loyalty/offers/",
        },
    }
    return render_loyalty_admin_view(
        request,
        title="Loyalty points",
        template_name="admin/industry/loyalty_home.html",
        context={"sections": sections},
    )
