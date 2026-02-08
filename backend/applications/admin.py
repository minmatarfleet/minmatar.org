from django.contrib import admin

from applications.models import EveCorporationApplication


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
