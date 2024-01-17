from django.contrib import admin

from .models import (
    EveAlliance,
    EveCharacter,
    EveCharacterSkillset,
    EveCorporation,
    EveCorporationApplication,
)

# Register your models here.
admin.site.register(EveCorporation)
admin.site.register(EveCharacter)
admin.site.register(EveCharacterSkillset)
admin.site.register(EveCorporationApplication)
admin.site.register(EveAlliance)
