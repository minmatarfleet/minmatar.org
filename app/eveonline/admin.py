from django.contrib import admin
from .models import EveCorporation, EveCorporationApplication, EveCharacter

# Register your models here.
admin.site.register(EveCorporation)
admin.site.register(EveCharacter)
admin.site.register(EveCorporationApplication)
