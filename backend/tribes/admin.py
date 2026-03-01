from django.contrib import admin

from tribes.models import (
    Tribe,
    TribeActivity,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupOutreach,
    TribeGroupRequirement,
    TribeGroupRequirementAssetType,
    TribeGroupRequirementSkill,
)


class TribeGroupInline(admin.TabularInline):
    model = TribeGroup
    extra = 0
    fields = ("name", "chief", "is_active", "discord_channel_id")
    show_change_link = True


@admin.register(Tribe)
class TribeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "chief", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ("chief", "group")
    inlines = [TribeGroupInline]


class AssetTypeInline(admin.TabularInline):
    model = TribeGroupRequirementAssetType
    extra = 1
    fields = ("eve_type", "minimum_count", "location_id")
    autocomplete_fields = ("eve_type",)
    verbose_name = "Qualifying Asset Type"
    verbose_name_plural = (
        "Qualifying Asset Types (any one satisfies the requirement)"
    )


class QualifyingSkillInline(admin.TabularInline):
    model = TribeGroupRequirementSkill
    extra = 1
    fields = ("eve_type", "minimum_level")
    autocomplete_fields = ("eve_type",)
    verbose_name = "Qualifying Skill"
    verbose_name_plural = "Required Skills (character must have ALL of these at their minimum level)"


class TribeGroupRequirementInline(admin.TabularInline):
    model = TribeGroupRequirement
    extra = 0
    show_change_link = True
    fields = ()


@admin.register(TribeGroup)
class TribeGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "tribe", "chief", "is_active")
    list_filter = ("is_active", "tribe")
    search_fields = ("name", "tribe__name")
    raw_id_fields = ("tribe", "chief", "group")
    filter_horizontal = ("elders",)
    inlines = [TribeGroupRequirementInline]


@admin.register(TribeGroupRequirement)
class TribeGroupRequirementAdmin(admin.ModelAdmin):
    list_display = ("tribe_group",)
    raw_id_fields = ("tribe_group",)
    inlines = [AssetTypeInline, QualifyingSkillInline]


class TribeGroupMembershipCharacterInline(admin.TabularInline):
    model = TribeGroupMembershipCharacter
    extra = 0
    fields = ("character", "committed_at", "left_at", "leave_reason")
    readonly_fields = ("committed_at",)
    raw_id_fields = ("character",)


@admin.register(TribeGroupMembership)
class TribeGroupMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "tribe_group",
        "status",
        "created_at",
        "approved_by",
    )
    list_filter = ("status", "tribe_group__tribe")
    search_fields = ("user__username", "tribe_group__name")
    raw_id_fields = ("user", "tribe_group", "approved_by", "removed_by")
    readonly_fields = ("created_at",)
    inlines = [TribeGroupMembershipCharacterInline]


@admin.register(TribeGroupMembershipCharacter)
class TribeGroupMembershipCharacterAdmin(admin.ModelAdmin):
    list_display = (
        "character",
        "membership",
        "committed_at",
        "left_at",
        "leave_reason",
    )
    list_filter = ("leave_reason",)
    search_fields = ("character__character_name",)
    raw_id_fields = ("membership", "character")
    readonly_fields = ("committed_at",)


@admin.register(TribeActivity)
class TribeActivityAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "tribe_group",
        "activity_type",
        "quantity",
        "unit",
        "created_at",
    )
    list_filter = ("activity_type", "tribe_group__tribe")
    search_fields = ("user__username", "reference_id")
    raw_id_fields = ("tribe_group", "user", "character")
    readonly_fields = ("created_at",)


@admin.register(TribeGroupOutreach)
class TribeGroupOutreachAdmin(admin.ModelAdmin):
    list_display = ("character", "tribe_group", "sent_by", "sent_at")
    list_filter = ("tribe_group__tribe",)
    search_fields = ("character__character_name", "sent_by__username")
    raw_id_fields = ("tribe_group", "character", "sent_by")
    readonly_fields = ("sent_at",)
