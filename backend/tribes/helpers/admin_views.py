"""Shared helpers for tribes admin custom views."""

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from tribes.helpers.admin_permissions import require_view_perm
from tribes.models import TribeGroup


def get_tribe_group_or_redirect(request, group_id):
    tribe_group = (
        TribeGroup.objects.select_related("tribe", "chief")
        .filter(pk=group_id)
        .first()
    )
    if not tribe_group:
        messages.error(request, "Tribe group not found.")
        return None, HttpResponseRedirect(reverse("admin:index"))
    return tribe_group, None


def render_tribe_group_view(
    request,
    *,
    tribe_group,
    title: str,
    template_name: str,
    context: dict,
    view_perm: str,
):
    require_view_perm(request.user, view_perm)
    context = {
        **admin.site.each_context(request),
        "title": title,
        "tribe_group": tribe_group,
        **context,
    }
    return TemplateResponse(request, template_name, context)
