"""Shared helpers for help tickets admin custom views."""

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from help_tickets.helpers.admin_permissions import (
    require_help_tickets_admin_view,
)
from help_tickets.models import HelpRequestCategory


def get_category_or_redirect(request, category_id):
    category = (
        HelpRequestCategory.objects.select_related(
            "tribe_group__tribe", "tribe_group__chief"
        )
        .filter(pk=category_id)
        .first()
    )
    if not category:
        messages.error(request, "Help category not found.")
        return None, HttpResponseRedirect(reverse("admin:index"))
    return category, None


def render_help_tickets_view(
    request,
    *,
    title: str,
    template_name: str,
    context: dict,
):
    require_help_tickets_admin_view(request.user)
    context = {
        **admin.site.each_context(request),
        "title": title,
        **context,
    }
    return TemplateResponse(request, template_name, context)
