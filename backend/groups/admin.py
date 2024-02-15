from django.contrib import admin

from .models import AutoGroup, RequestableGroup

# Register your models here.
admin.site.register(RequestableGroup)
admin.site.register(AutoGroup)
