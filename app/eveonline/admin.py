from django.contrib import admin
from .models import EveCorporation, EveCorporationApplication

# Register your models here.
admin.site.register(EveCorporation)
admin.site.register(EveCorporationApplication)
