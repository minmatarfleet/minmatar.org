from django.contrib import admin

from .models import Sig, Team, AffiliationType, UserAffiliation

# Register your models here.
admin.site.register(AffiliationType)
admin.site.register(UserAffiliation)
admin.site.register(Sig)
admin.site.register(Team)
