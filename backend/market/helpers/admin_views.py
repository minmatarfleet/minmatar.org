"""Shared helpers for market location admin views."""

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from eveonline.models import EveLocation

from market.helpers.permissions import require_change_perm, require_view_perm


def get_location_or_redirect(request, location_id):
    location = EveLocation.objects.filter(pk=location_id).first()
    if not location:
        messages.error(request, "Location not found.")
        return None, HttpResponseRedirect(reverse("admin:index"))
    return location, None


def redirect_preserving_query(request, url_name: str, location_pk: int):
    redirect_url = reverse(url_name, args=[location_pk])
    query = request.GET.urlencode()
    if query:
        redirect_url = f"{redirect_url}?{query}"
    return HttpResponseRedirect(redirect_url)


def render_location_view(
    request,
    *,
    location,
    title: str,
    template_name: str,
    context: dict,
    view_perm: str,
):
    require_view_perm(request.user, view_perm)
    context = {
        **admin.site.each_context(request),
        "title": title,
        "location": location,
        **context,
    }
    return TemplateResponse(request, template_name, context)


def handle_location_post(
    request,
    *,
    location,
    url_name: str,
    change_perm: str,
    save_fn,
    success_message: str,
    allowed_ids: set[int] | None = None,
):
    require_change_perm(request.user, change_perm)
    save_fn(location, request.POST, allowed_ids=allowed_ids)
    messages.success(request, success_message)
    return redirect_preserving_query(request, url_name, location.pk)
