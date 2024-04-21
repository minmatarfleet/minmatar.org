from django.contrib import admin

from .models import EveFleet, EveFleetNotificationChannel

# Register your models here.
admin.site.register(EveFleet)
admin.site.register(EveFleetNotificationChannel)
