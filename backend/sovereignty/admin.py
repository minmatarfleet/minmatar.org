from django.contrib import admin

from sovereignty.models import (
    SystemBaseResources,
    SystemSovereigntyConfig,
    SovereigntyUpgradeType,
    SystemSovereigntyUpgrade,
)


class SystemSovereigntyUpgradeInline(admin.TabularInline):
    model = SystemSovereigntyUpgrade
    extra = 0
    autocomplete_fields = ("upgrade_type",)


@admin.register(SystemSovereigntyConfig)
class SystemSovereigntyConfigAdmin(admin.ModelAdmin):
    list_display = ("system_id", "system_name")
    search_fields = ("system_name",)
    inlines = [SystemSovereigntyUpgradeInline]


@admin.register(SovereigntyUpgradeType)
class SovereigntyUpgradeTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "power_cost",
        "workforce_cost",
        "mining_upgrade_level",
    )
    list_filter = ("mining_upgrade_level",)
    search_fields = ("name",)


@admin.register(SystemSovereigntyUpgrade)
class SystemSovereigntyUpgradeAdmin(admin.ModelAdmin):
    list_display = ("system", "upgrade_type")
    list_filter = ("upgrade_type",)
    autocomplete_fields = ("system", "upgrade_type")


@admin.register(SystemBaseResources)
class SystemBaseResourcesAdmin(admin.ModelAdmin):
    list_display = ("system_id", "base_power", "base_workforce")
    search_fields = ("system_id",)
