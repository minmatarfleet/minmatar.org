from django.contrib import admin

from esi_health.models import EsiMessage, ScopeRollout


@admin.register(ScopeRollout)
class ScopeRolloutAdmin(admin.ModelAdmin):
    list_display = ("scope", "scope_group", "label", "added_on", "mode")
    list_filter = ("scope_group", "mode")
    search_fields = ("scope", "label")
    raw_id_fields = ("updated_by",)


@admin.register(EsiMessage)
class EsiMessageAdmin(admin.ModelAdmin):
    list_display = ("user", "sent_by", "sent_at", "characters")
    search_fields = ("user__username", "sent_by__username")
    raw_id_fields = ("user", "sent_by")
