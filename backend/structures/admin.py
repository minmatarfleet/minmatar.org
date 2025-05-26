from django.contrib import admin

from .forms import EveStructureTimerForm
from .models import (
    EveStructure,
    EveStructureTimer,
    EveStructureManager,
    EveStructurePing,
)

admin.site.register(EveStructure)
admin.site.register(EveStructurePing)


@admin.register(EveStructureTimer)
class StructureTimerAdmin(admin.ModelAdmin):
    form = EveStructureTimerForm
    list_display = ("name", "state")


@admin.register(EveStructureManager)
class StructureManagerAdmin(admin.ModelAdmin):
    """Admin page for EveStructureManager"""

    list_display = (
        "id",
        "corporation__name",
        "character__character_name",
        "poll_time",
        "last_polled",
    )
    search_fields = ("corporation__name", "character__character_name")
    list_filter = ["poll_time"]
    list_display_links = (
        "id",
        "corporation__name",
        "character__character_name",
    )
