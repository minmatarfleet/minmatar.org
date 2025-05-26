from django.contrib import admin

from .forms import EveStructureTimerForm
from .models import EveStructure, EveStructureTimer, EveStructureManager

admin.site.register(EveStructure)
admin.site.register(EveStructureManager)


@admin.register(EveStructureTimer)
class StructureTimerAdmin(admin.ModelAdmin):
    form = EveStructureTimerForm
    list_display = ("name", "state")
