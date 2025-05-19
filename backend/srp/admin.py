from django.contrib import admin

from .models import EveFleetShipReimbursement


@admin.register(EveFleetShipReimbursement)
class SrpAdmin(admin.ModelAdmin):
    """Admin page for SRP"""

    list_display = (
        "user__username",
        "fleet__created_by__username",
        "character_name",
        "ship_name",
        "killmail_id",
        "status",
    )
    search_fields = ("character_name", "ship_name", "killmail_id")
    list_filter = ["status"]
