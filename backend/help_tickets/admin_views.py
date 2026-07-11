"""Custom help tickets admin views."""

from django.urls import reverse

from help_tickets.helpers.admin_urls import changelist_url
from help_tickets.helpers.admin_views import (
    get_category_or_redirect,
    render_help_tickets_view,
)
from help_tickets.helpers.panel import (
    build_help_ticket_panel_config,
    compute_panel_content_hash,
)
from help_tickets.models import (
    HelpRequestCategory,
    HelpTicket,
    HelpTicketPanel,
)


def _panel_is_stale(panel: HelpTicketPanel) -> bool:
    if not panel.content_hash:
        return True
    current_hash = compute_panel_content_hash(build_help_ticket_panel_config())
    return panel.content_hash != current_hash


def _build_category_hub_sections(category: HelpRequestCategory) -> dict:
    category_id = category.pk
    category_filter = {"category__id__exact": category_id}
    open_filter = {**category_filter, "status__exact": HelpTicket.STATUS_OPEN}
    closed_filter = {
        **category_filter,
        "status__exact": HelpTicket.STATUS_CLOSED,
    }

    sections = {
        "settings": {
            "edit_url": reverse(
                "admin:help_tickets_helprequestcategory_change",
                args=[category_id],
            ),
        },
        "open_tickets": {
            "count": category.tickets.filter(
                status=HelpTicket.STATUS_OPEN
            ).count(),
            "list_url": changelist_url("helpticket", **open_filter),
        },
        "all_tickets": {
            "count": category.tickets.count(),
            "list_url": changelist_url("helpticket", **category_filter),
        },
        "closed_tickets": {
            "count": category.tickets.filter(
                status=HelpTicket.STATUS_CLOSED
            ).count(),
            "list_url": changelist_url("helpticket", **closed_filter),
        },
    }
    if category.tribe_group_id:
        sections["tribe_group"] = {
            "hub_url": reverse(
                "admin:tribes_group_hub", args=[category.tribe_group_id]
            ),
            "name": category.tribe_group.name,
            "tribe_name": category.tribe_group.tribe.name,
        }
    return sections


def help_tickets_home_view(request):
    panel = HelpTicketPanel.get_solo()
    panel_edit_url = reverse(
        "admin:help_tickets_helpticketpanel_change", args=[panel.pk]
    )
    categories = HelpRequestCategory.objects.select_related(
        "tribe_group__tribe"
    ).order_by("sort_order", "title")
    category_rows = []
    for category in categories:
        category_rows.append(
            {
                "category": category,
                "open_count": category.tickets.filter(
                    status=HelpTicket.STATUS_OPEN
                ).count(),
                "hub_url": reverse(
                    "admin:help_tickets_category_hub", args=[category.pk]
                ),
            }
        )
    ticket_queryset = HelpTicket.objects.select_related("category").order_by(
        "-opened_at"
    )
    tickets_truncated = ticket_queryset.count() > 100
    tickets = ticket_queryset[:100]
    ticket_rows = [
        {
            "ticket": ticket,
            "edit_url": reverse(
                "admin:help_tickets_helpticket_change", args=[ticket.pk]
            ),
        }
        for ticket in tickets
    ]
    return render_help_tickets_view(
        request,
        title="Help tickets",
        template_name="admin/help_tickets/home.html",
        context={
            "panel": panel,
            "panel_edit_url": panel_edit_url,
            "panel_is_stale": _panel_is_stale(panel),
            "category_rows": category_rows,
            "ticket_rows": ticket_rows,
            "tickets_truncated": tickets_truncated,
            "add_category_url": reverse(
                "admin:help_tickets_helprequestcategory_add"
            ),
            "all_tickets_url": changelist_url("helpticket"),
        },
    )


def help_category_hub_view(request, category_id):
    category, redirect = get_category_or_redirect(request, category_id)
    if redirect:
        return redirect
    return render_help_tickets_view(
        request,
        title=f"Help category — {category.title}",
        template_name="admin/help_tickets/category_hub.html",
        context={
            "category": category,
            "sections": _build_category_hub_sections(category),
            "assignee_count": category.assignees.count(),
        },
    )
