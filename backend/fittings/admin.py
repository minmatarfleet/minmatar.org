from django.contrib import admin
from django.db.models import Count, Exists, OuterRef, Subquery
from django.urls import reverse
from django.utils.html import format_html
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter

from eveuniverse.models import EveType

from .forms import EveDoctrineForm, EveFittingAdminForm
from .models import (
    EveDoctrine,
    EveDoctrineFitting,
    EveFitting,
    EveFittingHistory,
    EveFittingRefit,
    FittingTag,
)


class FittingTagListFilter(admin.SimpleListFilter):
    title = "tag"
    parameter_name = "fitting_tag"

    def lookups(self, request, model_admin):
        return FittingTag.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(tags__contains=[self.value()])
        return queryset


class HasRefitsListFilter(admin.SimpleListFilter):
    title = "has refits"
    parameter_name = "has_refits"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                Exists(
                    EveFittingRefit.objects.filter(
                        base_fitting_id=OuterRef("pk")
                    )
                )
            )
        if self.value() == "no":
            return queryset.filter(
                ~Exists(
                    EveFittingRefit.objects.filter(
                        base_fitting_id=OuterRef("pk")
                    )
                )
            )
        return queryset


class EveFittingRefitInline(admin.StackedInline):
    model = EveFittingRefit
    extra = 0
    show_change_link = True
    fields = (
        "name",
        "eft_format",
        "description",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(EveFitting)
class EveFittingAdmin(SafeDeleteAdmin):
    """Admin screen for EveFitting entity. Ship is inferred from EFT; display name is editable."""

    form = EveFittingAdminForm
    field_to_highlight = "name"

    list_display = (
        "highlight_deleted_field",
        "ship_name",
        "refit_count",
        "description",
        "deleted",
    )
    search_fields = ("name", "description", "aliases")
    list_filter = (
        SafeDeleteAdminFilter,
        HasRefitsListFilter,
        FittingTagListFilter,
    )
    list_per_page = 50
    ordering = ("name",)
    readonly_fields = (
        "ship_id",
        "latest_version",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Fitting",
            {
                "fields": (
                    "name",
                    "ship_id",
                    "latest_version",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
        (
            "EFT & description",
            {
                "fields": ("eft_format", "description", "tags"),
            },
        ),
        (
            "Aliases",
            {
                "description": (
                    "Used when resolving contracts and search; not shown on the public "
                    "fitting name."
                ),
                "fields": ("aliases",),
            },
        ),
        (
            "Pods",
            {
                "fields": ("minimum_pod", "recommended_pod"),
            },
        ),
    )
    inlines = (EveFittingRefitInline,)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        ship_sq = EveType.objects.filter(pk=OuterRef("ship_id")).values(
            "name"
        )[:1]
        return qs.annotate(
            _refit_count=Count("refits"),
            _ship_name=Subquery(ship_sq),
        )

    @admin.display(description="Ship", ordering="_ship_name")
    def ship_name(self, obj):
        return getattr(obj, "_ship_name", None) or "—"

    @admin.display(description="Refits", ordering="_refit_count")
    def refit_count(self, obj):
        return getattr(obj, "_refit_count", 0)

    def save_model(self, request, obj, form, change):
        eft_format = form.cleaned_data.get("eft_format") or getattr(
            obj, "eft_format", ""
        )
        if eft_format and eft_format.strip():
            derived_name = EveFitting.fitting_name_from_eft(eft_format)
            if not (obj.name and str(obj.name).strip()) and derived_name:
                obj.name = derived_name
            ship_name = EveFitting.ship_name_from_eft(eft_format)
            if ship_name:
                eve_type = EveType.objects.filter(name=ship_name).first()
                if eve_type is not None:
                    obj.ship_id = eve_type.id
        super().save_model(request, obj, form, change)


EveFittingAdmin.highlight_deleted_field.short_description = "Name"


@admin.register(EveFittingHistory)
class EveFittingHistoryAdmin(admin.ModelAdmin):
    """Read-only audit of previous fitting versions."""

    list_display = (
        "fitting",
        "superseded_version_id",
        "name",
        "created_at",
    )
    list_filter = ("fitting",)
    search_fields = ("name", "superseded_version_id", "fitting__name")
    raw_id_fields = ("fitting",)
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "fitting",
        "superseded_version_id",
        "name",
        "ship_id",
        "eft_format",
        "description",
        "aliases",
        "minimum_pod",
        "recommended_pod",
        "tags",
        "created_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(EveFittingRefit)
class EveFittingRefitAdmin(admin.ModelAdmin):
    """Admin screen for EveFittingRefit entity"""

    list_display = ("name", "base_fitting_link", "updated_at")
    list_filter = ("base_fitting",)
    search_fields = ("name", "description", "base_fitting__name")
    autocomplete_fields = ("base_fitting",)
    ordering = ("base_fitting", "name")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Base", {"fields": ("base_fitting",)}),
        ("Refit", {"fields": ("name", "eft_format", "description")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Base fitting", ordering="base_fitting")
    def base_fitting_link(self, obj):
        if obj.base_fitting_id:
            url = reverse(
                "admin:fittings_evefitting_change", args=[obj.base_fitting_id]
            )
            return format_html('<a href="{}">{}</a>', url, obj.base_fitting)
        return "—"


@admin.register(EveDoctrine)
class EveDoctrineAdmin(admin.ModelAdmin):
    """
    Custom admin to make editing doctrines easier
    """

    form = EveDoctrineForm
    list_display = ("name", "type", "description")
    search_fields = ("name", "type", "description")
    ordering = ("name",)

    def save_model(self, request, obj, form, change):
        obj.save()
        doctrine_id = obj.id
        primary_doctrine_fittings = [
            doctrine_fitting.fitting
            for doctrine_fitting in EveDoctrineFitting.objects.filter(
                doctrine_id=doctrine_id, role="primary"
            )
        ]
        secondary_doctrine_fittings = [
            doctrine_fitting.fitting
            for doctrine_fitting in EveDoctrineFitting.objects.filter(
                doctrine_id=doctrine_id, role="secondary"
            )
        ]
        support_doctrine_fittings = [
            doctrine_fitting.fitting
            for doctrine_fitting in EveDoctrineFitting.objects.filter(
                doctrine_id=doctrine_id, role="support"
            )
        ]
        for fitting in form.cleaned_data["primary_fittings"]:
            EveDoctrineFitting.objects.get_or_create(
                doctrine=obj, fitting=fitting, role="primary"
            )
        for fitting in form.cleaned_data["secondary_fittings"]:
            EveDoctrineFitting.objects.get_or_create(
                doctrine=obj, fitting=fitting, role="secondary"
            )
        for fitting in form.cleaned_data["support_fittings"]:
            EveDoctrineFitting.objects.get_or_create(
                doctrine=obj, fitting=fitting, role="support"
            )

        # delete fittings that were removed
        for fitting in primary_doctrine_fittings:
            if fitting not in form.cleaned_data["primary_fittings"]:
                EveDoctrineFitting.objects.filter(
                    doctrine=obj, fitting=fitting, role="primary"
                ).delete()

        for fitting in secondary_doctrine_fittings:
            if fitting not in form.cleaned_data["secondary_fittings"]:
                EveDoctrineFitting.objects.filter(
                    doctrine=obj, fitting=fitting, role="secondary"
                ).delete()

        for fitting in support_doctrine_fittings:
            if fitting not in form.cleaned_data["support_fittings"]:
                EveDoctrineFitting.objects.filter(
                    doctrine=obj, fitting=fitting, role="support"
                ).delete()

        # Handle ManyToMany fields (locations)
        obj.locations.set(form.cleaned_data["locations"])
