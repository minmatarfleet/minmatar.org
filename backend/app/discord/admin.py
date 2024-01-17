from django.contrib import admin

from .models import DiscordRole, DiscordUser

# Register your models here.
admin.site.register(DiscordUser)
admin.site.register(DiscordRole)
