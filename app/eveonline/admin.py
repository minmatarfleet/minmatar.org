from django.contrib import admin
from .models import (
    EveCorporation,
    EveCorporationApplication,
    EveCharacter,
    EveCharacterSkillset,
    EveGroup,
    EveAlliance
)

# Register your models here.
admin.site.register(EveCorporation)
admin.site.register(EveCharacter)
admin.site.register(EveCharacterSkillset)
admin.site.register(EveCorporationApplication)
admin.site.register(EveGroup)
admin.site.register(EveAlliance)
