from django.contrib import admin

from .models import EveFleet, EveFleetAudience, EveFleetLocation

# Register your models here.
admin.site.register(EveFleet)
admin.site.register(EveFleetLocation)
admin.site.register(EveFleetAudience)
