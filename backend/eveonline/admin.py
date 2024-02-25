from django.contrib import admin

from .models import EveAlliance, EveCharacter, EveCorporation, EveSkillset

# Register your models here.
admin.site.register(EveCorporation)
admin.site.register(EveCharacter)
admin.site.register(EveSkillset)
admin.site.register(EveAlliance)
