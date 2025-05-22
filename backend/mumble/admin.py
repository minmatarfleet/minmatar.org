from django.contrib import admin

from .models import MumbleAccess


class MumbleAccessAdmin(admin.ModelAdmin):
    list_display = [
        "username",
        "user__username",
        "suspended",
    ]
    search_fields = ["username"]


admin.site.register(MumbleAccess, MumbleAccessAdmin)
