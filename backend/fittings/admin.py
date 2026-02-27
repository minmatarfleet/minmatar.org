from django.contrib import admin

from eveuniverse.models import EveType

from .forms import EveDoctrineForm
from .models import (
    EveDoctrine,
    EveDoctrineFitting,
    EveFitting,
    EveFittingRefit,
)


@admin.register(EveFitting)
class EveFittingAdmin(admin.ModelAdmin):
    """Admin screen for EveFitting entity"""

    list_display = ("name", "ship_id", "description")
    search_fields = ("name", "description", "aliases")
    list_filter = ("ship_id",)
    list_per_page = 50
    ordering = ("name",)

    def save_model(self, request, obj, form, change):
        eft_format = form.cleaned_data.get("eft_format") or getattr(
            obj, "eft_format", ""
        )
        if eft_format and eft_format.strip():
            obj.name = EveFitting.fitting_name_from_eft(eft_format)
            ship_name = EveFitting.ship_name_from_eft(eft_format)
            if ship_name:
                eve_type = EveType.objects.filter(name=ship_name).first()
                if eve_type is not None:
                    obj.ship_id = eve_type.id
        super().save_model(request, obj, form, change)


@admin.register(EveFittingRefit)
class EveFittingRefitAdmin(admin.ModelAdmin):
    """Admin screen for EveFittingRefit entity"""

    list_display = ("name", "base_fitting", "updated_at")
    list_filter = ("base_fitting",)
    search_fields = ("name", "description", "base_fitting__name")
    raw_id_fields = ("base_fitting",)
    ordering = ("base_fitting", "name")


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

        # Handle ManyToMany fields (sigs and locations)
        obj.sigs.set(form.cleaned_data["sigs"])
        obj.locations.set(form.cleaned_data["locations"])
