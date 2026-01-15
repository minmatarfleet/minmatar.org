from django.contrib import admin

from .models import EveFreightRoute, EveFreightRouteOption


class FreightRouteAdmin(admin.ModelAdmin):
    """Custom admin model for EveFreightRoute entities"""

    list_display = [
        "origin_location__location_name",
        "destination_location__location_name",
        "bidirectional",
        "active",
    ]


admin.site.register(EveFreightRoute, FreightRouteAdmin)
admin.site.register(EveFreightRouteOption)
