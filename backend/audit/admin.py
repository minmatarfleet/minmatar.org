from django.contrib import admin

from audit.models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    """Admin screen for AuditEntry entity"""

    list_display = (
        "id",
        "created_at",
        "category",
        "summary",
        "user__username",
        "character__character_name",
    )

    search_fields = ("character__character_name", "user__username", "summary")
    list_filter = ["category"]
    date_hierarchy = "created_at"
