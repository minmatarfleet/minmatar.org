from django.contrib import admin
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.http import urlencode

from eveonline.models import EveLocation

from freight.helpers.permissions import (
    VIEW_FREIGHT_LOCATIONS,
    index_link_perms,
    require_view_perm,
)

from .models import EveFreightRoute

FREIGHT_EXTRA_INDEX_LINKS = [
    {
        "name": "Freight locations",
        "admin_url": "admin:freight_locations",
        "view_only": True,
    },
]

_STAGING_EVEONLINE_MODELS = {"evelocation"}


def _build_freight_index_models(models: list[dict], request) -> list[dict]:
    del models
    index_models = []
    for extra in FREIGHT_EXTRA_INDEX_LINKS:
        index_models.append(
            {
                "name": extra["name"],
                "object_name": extra["name"],
                "perms": index_link_perms(
                    request.user,
                    view_perm=extra.get("view_perm", VIEW_FREIGHT_LOCATIONS),
                ),
                "admin_url": reverse(extra["admin_url"]),
                "view_only": extra.get("view_only", False),
            }
        )
    return index_models


def _route_changelist_url(**filters) -> str:
    base = reverse("admin:freight_evefreightroute_changelist")
    if not filters:
        return base
    return f"{base}?{urlencode(filters)}"


def _route_add_url(**initial) -> str:
    base = reverse("admin:freight_evefreightroute_add")
    if not initial:
        return base
    return f"{base}?{urlencode(initial)}"


@admin.register(EveFreightRoute)
class FreightRouteAdmin(admin.ModelAdmin):
    """Freight route pricing and timing between two alliance locations."""

    list_display = (
        "origin_location",
        "destination_location",
        "isk_per_m3",
        "collateral_modifier",
        "expiration_days",
        "days_to_complete",
        "active",
    )
    list_filter = ("active", "origin_location", "destination_location")
    list_per_page = 50
    search_fields = (
        "origin_location__location_name",
        "origin_location__short_name",
        "destination_location__location_name",
        "destination_location__short_name",
    )
    autocomplete_fields = ("origin_location", "destination_location")
    ordering = (
        "origin_location__location_name",
        "destination_location__location_name",
    )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        origin_id = request.GET.get("origin_location")
        destination_id = request.GET.get("destination_location")
        if origin_id:
            initial["origin_location"] = int(origin_id)
        if destination_id:
            initial["destination_location"] = int(destination_id)
        return initial


def freight_locations_view(request):
    require_view_perm(request.user, VIEW_FREIGHT_LOCATIONS)
    locations = (
        EveLocation.objects.filter(freight_active=True)
        .annotate(
            outbound_route_count=Count(
                "origin_freight_routes",
                filter=Q(origin_freight_routes__active=True),
            ),
            inbound_route_count=Count(
                "destination_freight_routes",
                filter=Q(destination_freight_routes__active=True),
            ),
        )
        .order_by("location_name")
    )
    rows = []
    for location in locations:
        rows.append(
            {
                "location": location,
                "hub_url": reverse(
                    "admin:freight_location_hub", args=[location.pk]
                ),
                "outbound_route_count": location.outbound_route_count,
                "inbound_route_count": location.inbound_route_count,
            }
        )
    context = {
        **admin.site.each_context(request),
        "title": "Freight locations",
        "rows": rows,
    }
    return TemplateResponse(
        request, "admin/freight/locations_list.html", context
    )


def freight_location_hub_view(request, location_id):
    require_view_perm(request.user, VIEW_FREIGHT_LOCATIONS)
    location = EveLocation.objects.filter(pk=location_id).first()
    if not location:
        messages.error(request, "Location not found.")
        return HttpResponseRedirect(reverse("admin:index"))

    outbound_routes = EveFreightRoute.objects.filter(
        origin_location=location
    ).select_related("destination_location")
    inbound_routes = EveFreightRoute.objects.filter(
        destination_location=location
    ).select_related("origin_location")

    context = {
        **admin.site.each_context(request),
        "title": f"Freight — {location.location_name}",
        "location": location,
        "outbound_active_count": outbound_routes.filter(active=True).count(),
        "outbound_total_count": outbound_routes.count(),
        "inbound_active_count": inbound_routes.filter(active=True).count(),
        "inbound_total_count": inbound_routes.count(),
        "outbound_routes_url": _route_changelist_url(
            origin_location__id__exact=location.pk
        ),
        "inbound_routes_url": _route_changelist_url(
            destination_location__id__exact=location.pk
        ),
        "add_outbound_route_url": _route_add_url(origin_location=location.pk),
        "add_inbound_route_url": _route_add_url(
            destination_location=location.pk
        ),
    }
    return TemplateResponse(
        request, "admin/freight/location_hub.html", context
    )


def _get_custom_freight_admin_urls():
    return [
        path(
            "freight/locations/",
            admin.site.admin_view(freight_locations_view),
            name="freight_locations",
        ),
        path(
            "freight/location/<int:location_id>/",
            admin.site.admin_view(freight_location_hub_view),
            name="freight_location_hub",
        ),
    ]


def _apply_freight_app_list(app_list, request):
    for app in app_list:
        if app["name"] == "Staging Systems":
            if not any(
                model["name"] == "Freight locations" for model in app["models"]
            ):
                app["models"] = list(
                    app["models"]
                ) + _build_freight_index_models([], request)
        elif app["app_label"] == "freight":
            index_models = _build_freight_index_models(app["models"], request)
            if index_models:
                app["models"] = index_models
        elif app["name"] == "Supply":
            app["models"] = [
                model
                for model in app["models"]
                if model["object_name"].lower() != "evefreightroute"
            ]
    return app_list


_FREIGHT_ADMIN_PATCHED_ATTR = "freight_admin_patched"


def apply_freight_admin_customizations():
    """Chain freight admin URLs and sidebar after market/industry patches."""
    if getattr(admin.site, _FREIGHT_ADMIN_PATCHED_ATTR, False):
        return

    freight_previous_get_app_list = admin.site.get_app_list

    def _freight_get_app_list(request, app_label=None):
        app_list = freight_previous_get_app_list(request, app_label)
        return _apply_freight_app_list(app_list, request)

    admin.site.get_app_list = _freight_get_app_list

    freight_previous_get_urls = admin.site.get_urls

    def _freight_get_urls():
        return _get_custom_freight_admin_urls() + freight_previous_get_urls()

    admin.site.get_urls = _freight_get_urls
    setattr(admin.site, _FREIGHT_ADMIN_PATCHED_ATTR, True)
