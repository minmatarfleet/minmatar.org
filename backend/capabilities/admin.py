"""Admin views to sanity-check computed capabilities. Everything is read-only:
the Celery tasks own these tables. Corrections go on the fitting page."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from capabilities.models import (
    CharacterAccount,
    CharacterAccountLink,
    CharacterAccountMember,
    CharacterCapability,
    CharacterFittingReadiness,
    FittingRequirementSet,
    SdeSnapshot,
)
from fittings.admin import render_skill_requirements


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SdeSnapshot)
class SdeSnapshotAdmin(ReadOnlyAdmin):
    list_display = ("build", "release_date", "is_current", "size", "loaded_at")
    fields = (
        "build",
        "release_date",
        "is_current",
        "size",
        "loaded_at",
        "changes",
    )
    readonly_fields = fields


@admin.register(FittingRequirementSet)
class FittingRequirementSetAdmin(ReadOnlyAdmin):
    list_display = (
        "fitting",
        "capability",
        "capability_source",
        "strategic",
        "rows_count",
        "proven_pilots",
        "proven_pass",
        "doctrine_ready",
        "sde_build",
        "computed_at",
    )
    list_filter = (
        "is_current",
        "capability",
        "strategic",
        "capability_source",
    )
    search_fields = ("fitting__name",)
    fields = (
        "fitting_link",
        "capability",
        "capability_source",
        "strategic",
        "tank_layers",
        "proven_pilots",
        "proven_pass",
        "unknown_items",
        "sde_build",
        "rules_version",
        "fitting_version",
        "is_current",
        "computed_at",
        "requirements",
    )
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("fitting")

    @admin.display(description="Rows")
    def rows_count(self, obj):
        return obj.rows.count()

    @admin.display(description="Proven pilots passing core")
    def proven_pass(self, obj):
        if obj.proven_pass_rate is None:
            return "—"
        return f"{round(100 * obj.proven_pass_rate)}%"

    @admin.display(description="Doctrine-ready characters")
    def doctrine_ready(self, obj):
        return CharacterFittingReadiness.objects.filter(
            requirement_set=obj, doctrine_ready=True
        ).count()

    @admin.display(description="Fitting")
    def fitting_link(self, obj):
        url = reverse(
            "admin:fittings_evefitting_change", args=[obj.fitting_id]
        )
        return format_html(
            '<a href="{}">{} (edit corrections)</a>', url, obj.fitting
        )

    @admin.display(description="Requirements")
    def requirements(self, obj):
        return render_skill_requirements(obj.fitting)


@admin.register(CharacterFittingReadiness)
class CharacterFittingReadinessAdmin(ReadOnlyAdmin):
    list_display = (
        "character",
        "fitting",
        "unlocked",
        "hard_ready",
        "core_ready",
        "doctrine_ready",
        "fit_problems",
        "days_to_hard",
        "days_to_core",
        "support_score",
    )
    list_filter = ("doctrine_ready", "hard_ready", "core_ready", "fitting")
    search_fields = ("character__character_name", "fitting__name")
    list_select_related = ("character", "fitting")
    readonly_fields = [f.name for f in CharacterFittingReadiness._meta.fields]
    fields = readonly_fields


@admin.register(CharacterCapability)
class CharacterCapabilityAdmin(ReadOnlyAdmin):
    list_display = (
        "character",
        "capability",
        "level",
        "ready_fittings",
        "unlocked_fittings",
        "fleets_365d",
        "strategic_fleets_365d",
        "best_fitting",
        "last_flown",
    )
    list_filter = ("capability", "level")
    search_fields = ("character__character_name", "character__user__username")
    list_select_related = ("character", "best_fitting")
    readonly_fields = [f.name for f in CharacterCapability._meta.fields]
    fields = readonly_fields


class CharacterAccountMemberInline(admin.TabularInline):
    model = CharacterAccountMember
    extra = 0
    fields = ("character", "source")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CharacterAccount)
class CharacterAccountAdmin(ReadOnlyAdmin):
    list_display = ("user", "number", "source", "characters", "updated_at")
    list_filter = ("source",)
    search_fields = ("user__username", "members__character__character_name")
    inlines = (CharacterAccountMemberInline,)
    fields = ("user", "number", "source", "updated_at")
    readonly_fields = fields

    @admin.display(description="Characters")
    def characters(self, obj):
        return ", ".join(m.character.character_name for m in obj.members.all())


@admin.register(CharacterAccountLink)
class CharacterAccountLinkAdmin(ReadOnlyAdmin):
    list_display = (
        "user",
        "character_a",
        "character_b",
        "fleets_together",
        "last_seen_together",
    )
    search_fields = (
        "user__username",
        "character_a__character_name",
        "character_b__character_name",
    )
    list_select_related = ("user", "character_a", "character_b")
    readonly_fields = [f.name for f in CharacterAccountLink._meta.fields]
    fields = readonly_fields
