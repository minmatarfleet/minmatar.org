from django.contrib import admin

from intel.models import IntelReport


@admin.register(IntelReport)
class IntelReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "system_name", "reporter_name")
    list_filter = ("kind",)
    search_fields = ("system_name", "reporter_name", "public_id")
    readonly_fields = ("public_id", "created_at")
    raw_id_fields = ("reporter",)
