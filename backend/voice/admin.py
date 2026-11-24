from django.contrib import admin

from voice.models import (
    VoiceAuditEvent,
    VoiceBan,
    VoiceCertificate,
    VoiceChannelLease,
    VoiceGrant,
    VoiceIdentity,
)


class VoiceCertificateInline(admin.TabularInline):
    model = VoiceCertificate
    extra = 0
    readonly_fields = ("cert_hash", "created_at", "last_used_at")


@admin.register(VoiceIdentity)
class VoiceIdentityAdmin(admin.ModelAdmin):
    list_display = ("character_name", "character_id", "id", "created_at")
    search_fields = ("character_name", "character_id")
    readonly_fields = ("owner_hash",)
    inlines = [VoiceCertificateInline]


@admin.register(VoiceBan)
class VoiceBanAdmin(admin.ModelAdmin):
    list_display = (
        "character_name",
        "character_id",
        "reason",
        "created_at",
        "expires_at",
        "lifted_at",
    )
    search_fields = ("character_name", "character_id")


@admin.register(VoiceGrant)
class VoiceGrantAdmin(admin.ModelAdmin):
    list_display = ("character_id", "fleet", "source", "role", "expires_at")
    list_filter = ("source", "role")
    search_fields = ("character_id",)
    raw_id_fields = ("fleet",)


@admin.register(VoiceChannelLease)
class VoiceChannelLeaseAdmin(admin.ModelAdmin):
    list_display = (
        "branch",
        "fleet",
        "started_at",
        "release_after",
        "released_at",
    )
    raw_id_fields = ("fleet",)


@admin.register(VoiceAuditEvent)
class VoiceAuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "character_id", "fleet_id", "actor")
    list_filter = ("kind",)
    search_fields = ("character_id",)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
