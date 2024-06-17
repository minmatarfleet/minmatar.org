from django.contrib import admin

from .models import (
    EveFleet,
    EveFleetAudience,
    EveFleetLocation,
    EveFleetAudienceWebhook,
)

# Register your models here.
admin.site.register(EveFleet)
admin.site.register(EveFleetLocation)
admin.site.register(EveFleetAudience)
admin.site.register(EveFleetAudienceWebhook)
