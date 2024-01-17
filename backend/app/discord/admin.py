from django.contrib import admin
from .models import DiscordUser, DiscordRole

# Register your models here.
admin.site.register(DiscordUser)
admin.site.register(DiscordRole)