from django.contrib import admin

from .forms import EveStructureTimerForm
from .models import EveStructure, EveStructureTimer

admin.site.register(EveStructure)


@admin.register(EveStructureTimer)
class StructureTimerAdmin(admin.ModelAdmin):
    form = EveStructureTimerForm
    list_display = ("name", "state")
