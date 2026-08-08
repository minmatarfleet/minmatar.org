from django.contrib import admin

from alliance.models import AllianceHealthSnapshot


@admin.register(AllianceHealthSnapshot)
class AllianceHealthSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "computed_at")
    readonly_fields = ("computed_at", "payload")
