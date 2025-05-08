from django.contrib import admin

from .models import (
    EveFleet,
    EveFleetAudience,
    EveFleetAudienceWebhook,
    EveFleetLocation,
    EveFleetInstance,
    EveFleetInstanceMember,
)


class FleetAdmin(admin.ModelAdmin):
    date_hierarchy = "start_time"
    list_display = [
        "start_time",
        "status",
        "description",
        "created_by__username",
    ]
    list_filter = ["status"]
    search_fields = ["description"]


# Register your models here.
admin.site.register(EveFleet, FleetAdmin)
admin.site.register(EveFleetLocation)
admin.site.register(EveFleetAudience)
admin.site.register(EveFleetAudienceWebhook)
admin.site.register(EveFleetInstance)
admin.site.register(EveFleetInstanceMember)
