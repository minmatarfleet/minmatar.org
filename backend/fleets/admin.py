from django.contrib import admin

from .models import (
    EveFleet,
    EveFleetAudience,
    EveFleetLocation,
    EveFleetNotificationChannel,
)

# Register your models here.
admin.site.register(EveFleet)
admin.site.register(EveFleetNotificationChannel)
admin.site.register(EveFleetLocation)
admin.site.register(EveFleetAudience)
