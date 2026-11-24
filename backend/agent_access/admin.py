from django.contrib import admin, messages
from django.utils import timezone

from .keys import assign_new_key
from .models import (
    AgentDiscordCall,
    AgentDiscordPostTarget,
    AgentDiscordReadBlock,
    AgentDiscordSettings,
    AgentKey,
)


@admin.register(AgentKey)
class AgentKeyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "key_prefix",
        "can_write",
        "active",
        "expires_at",
        "last_used_at",
        "last_used_ip",
    )
    readonly_fields = (
        "key_prefix",
        "created_by",
        "created_at",
        "revoked_at",
        "last_used_at",
        "last_used_ip",
    )
    actions = ("revoke",)

    @admin.display(boolean=True)
    def active(self, obj):
        return obj.is_active

    def save_model(self, request, obj, form, change):
        if not change:
            raw = assign_new_key(obj)
            obj.created_by = request.user
            super().save_model(request, obj, form, change)
            messages.warning(
                request,
                f"New agent key (shown once, copy it now): {raw}",
            )
            return
        super().save_model(request, obj, form, change)

    @admin.action(description="Revoke selected keys")
    def revoke(self, request, queryset):
        count = queryset.filter(revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        messages.success(request, f"Revoked {count} key(s).")


@admin.register(AgentDiscordSettings)
class AgentDiscordSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "enabled",
        "writes_enabled",
        "writes_per_minute",
        "writes_per_day",
    )

    def has_add_permission(self, request):
        return not AgentDiscordSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AgentDiscordPostTarget)
class AgentDiscordPostTargetAdmin(admin.ModelAdmin):
    list_display = ("guild_id", "channel_id", "include_threads", "note")
    search_fields = ("guild_id", "channel_id", "note")


@admin.register(AgentDiscordReadBlock)
class AgentDiscordReadBlockAdmin(admin.ModelAdmin):
    list_display = ("guild_id", "channel_id", "note")
    search_fields = ("guild_id", "channel_id", "note")


@admin.register(AgentDiscordCall)
class AgentDiscordCallAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "key",
        "tool",
        "is_write",
        "ok",
        "guild_id",
        "channel_id",
        "error",
        "ip",
    )
    list_filter = ("tool", "is_write", "ok", "key")
    search_fields = ("guild_id", "channel_id", "error")
    date_hierarchy = "created_at"
    list_select_related = ("key",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
