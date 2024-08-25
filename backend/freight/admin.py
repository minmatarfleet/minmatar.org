from django.contrib import admin
from .models import EveFreightLocation, EveFreightRoute, EveFreightRouteOption

# Register your models here.
admin.site.register(EveFreightLocation)
admin.site.register(EveFreightRoute)
admin.site.register(EveFreightRouteOption)
