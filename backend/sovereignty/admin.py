from django.contrib import admin

from sovereignty.forms import SystemSovereigntyConfigAdminForm
from sovereignty.models import (
    SystemSovereigntyConfig,
    SystemSovereigntyUpgrade,
)
from sovereignty.services import (
    get_computed_power_workforce,
    get_base_power_workforce,
    register_system,
)
from sovereignty.utils import get_sovereignty_upgrade_types_queryset


class SystemSovereigntyUpgradeInline(admin.TabularInline):
    model = SystemSovereigntyUpgrade
    extra = 0

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "eve_type":
            kwargs["queryset"] = get_sovereignty_upgrade_types_queryset()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(SystemSovereigntyConfig)
class SystemSovereigntyConfigAdmin(admin.ModelAdmin):
    form = SystemSovereigntyConfigAdminForm
    list_display = (
        "system_name",
        "total_power_display",
        "total_workforce_display",
        "remaining_power_display",
        "remaining_workforce_display",
    )
    list_display_links = ("system_name",)
    search_fields = ("system_name", "system_id")
    inlines = [SystemSovereigntyUpgradeInline]
    readonly_fields = (
        "total_power_display",
        "total_workforce_display",
        "remaining_power_display",
        "remaining_workforce_display",
    )
    fieldsets = (
        (None, {"fields": ("system",)}),
        (
            "Resources",
            {
                "fields": (
                    "total_power_display",
                    "total_workforce_display",
                    "remaining_power_display",
                    "remaining_workforce_display",
                ),
                "description": "Total = base from system. Remaining = after upgrade costs and conversion.",
            },
        ),
    )

    @admin.display(description="Total power")
    def total_power_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        base_power, _ = get_base_power_workforce(obj.system_id)
        return base_power

    @admin.display(description="Total workforce")
    def total_workforce_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        _, base_workforce = get_base_power_workforce(obj.system_id)
        return base_workforce

    @admin.display(description="Remaining power")
    def remaining_power_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        power, _, _, _ = get_computed_power_workforce(obj.system_id)
        return power

    @admin.display(description="Remaining workforce")
    def remaining_workforce_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        _, workforce, _, _ = get_computed_power_workforce(obj.system_id)
        return workforce

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            # New system: ensure base resources exist and name is from universe
            config, _ = register_system(obj.system_id)
            # Refresh so list/redirect show resolved name
            obj.system_name = config.system_name
            obj.save(update_fields=["system_name"])
