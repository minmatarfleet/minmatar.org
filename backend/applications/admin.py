from django.contrib import admin

from applications.models import (
    CorporationRequirement,
    EveCorporationApplication,
)


class CorpApplicationAdmin(admin.ModelAdmin):
    """Custom admin model for EveCorporationApplication entities"""

    date_hierarchy = "created_at"
    list_display = [
        "id",
        "created_at",
        "user__username",
        "corporation_id",
        "status",
    ]
    list_filter = ["status"]
    search_fields = ["user__username", "corporation_id"]


admin.site.register(EveCorporationApplication, CorpApplicationAdmin)


@admin.register(CorporationRequirement)
class CorporationRequirementAdmin(admin.ModelAdmin):
    list_display = ("corporation", "kind", "who", "importance", "position")
    list_filter = ("kind", "importance")
    search_fields = ("corporation__name",)
    raw_id_fields = ("corporation", "created_by")
