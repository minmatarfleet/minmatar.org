from django.contrib import admin

from .models import EveStructure, EveStructureTimer

admin.site.register(EveStructure)


@admin.register(EveStructureTimer)
class StructureTimerAdmin(admin.ModelAdmin):
    list_display = ("name", "state")
