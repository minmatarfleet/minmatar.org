from typing import Any
from django.contrib import admin

from .models import EveDoctrine, EveFitting, EveFittingTag, EveDoctrineFitting
from .forms import EveDoctrineForm

admin.site.register(EveFitting)
admin.site.register(EveFittingTag)


@admin.register(EveDoctrine)
class EveDoctrineAdmin(admin.ModelAdmin):
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
