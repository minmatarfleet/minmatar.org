from django.contrib import admin

from .models import EveFreightRoute


class FreightRouteAdmin(admin.ModelAdmin):
    """Custom admin model for EveFreightRoute entities."""

    list_display = [
        "origin_location__location_name",
        "destination_location__location_name",
        "isk_per_m3",
        "collateral_modifier",
        "expiration_days",
        "days_to_complete",
        "active",
    ]


admin.site.register(EveFreightRoute, FreightRouteAdmin)
