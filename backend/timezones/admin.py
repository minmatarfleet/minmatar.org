"""Read-only admin to check assessments: timezones.services owns the rows."""

from django.contrib import admin

from timezones.models import PilotTimezone, TimezoneRole


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PilotTimezone)
class PilotTimezoneAdmin(ReadOnlyAdmin):
    list_display = (
        "user",
        "home",
        "home_source",
        "brackets",
        "inferred_home",
        "inferred_confidence",
        "declared_prime_time",
        "active_days",
        "eligible",
        "changed_at",
    )
    list_filter = ("eligible", "home", "home_source", "inferred_home")
    search_fields = ("user__username",)
    list_select_related = ("user",)


@admin.register(TimezoneRole)
class TimezoneRoleAdmin(ReadOnlyAdmin):
    list_display = ("code", "group")
