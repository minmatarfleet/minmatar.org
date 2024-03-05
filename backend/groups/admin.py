from django.contrib import admin

from .models import AutoGroup, Sig, Team

# Register your models here.
admin.site.register(AutoGroup)
admin.site.register(Sig)
admin.site.register(Team)
