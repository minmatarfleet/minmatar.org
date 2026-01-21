from django.contrib import admin

from .models import AffiliationType, EveCorporationGroup, Sig, Team

# Register your models here.
admin.site.register(AffiliationType)
admin.site.register(EveCorporationGroup)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description", "content")
    ordering = ("name",)
    filter_horizontal = ("directors", "members")


@admin.register(Sig)
class SigAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description", "content")
    ordering = ("name",)
    filter_horizontal = ("officers", "members")
