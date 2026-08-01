"""Shared helpers for industry admin custom views."""

from collections.abc import Callable

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from industry.helpers.admin_permissions import (
    require_industry_orders_admin_view,
    require_loyalty_admin_view,
)
from industry.models import IndustryOrder


def get_order_or_redirect(request, order_id):
    order = (
        IndustryOrder.objects.select_related("character", "location")
        .filter(pk=order_id)
        .first()
    )
    if not order:
        messages.error(request, "Industry order not found.")
        return None, HttpResponseRedirect(reverse("admin:index"))
    return order, None


def render_industry_admin_view(
    request,
    *,
    title: str,
    template_name: str,
    context: dict,
    require_fn: Callable[[object], None],
):
    require_fn(request.user)
    context = {
        **admin.site.each_context(request),
        "title": title,
        **context,
    }
    return TemplateResponse(request, template_name, context)


def render_industry_orders_view(
    request,
    *,
    title: str,
    template_name: str,
    context: dict,
):
    return render_industry_admin_view(
        request,
        title=title,
        template_name=template_name,
        context=context,
        require_fn=require_industry_orders_admin_view,
    )


def render_loyalty_admin_view(
    request,
    *,
    title: str,
    template_name: str,
    context: dict,
):
    return render_industry_admin_view(
        request,
        title=title,
        template_name=template_name,
        context=context,
        require_fn=require_loyalty_admin_view,
    )
