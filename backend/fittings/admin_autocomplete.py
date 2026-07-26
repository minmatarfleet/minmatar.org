"""Scoped admin autocomplete for fitting module substitutions."""

from django.contrib.admin.views.autocomplete import AutocompleteJsonView
from eveuniverse.models import EveType

from fittings.helpers.module_substitutions import (
    fitting_item_types,
    variant_types_for,
    variant_types_for_fitting_items,
)
from fittings.models import EveFitting, EveFittingModuleSubstitution


class ModuleSubstitutionAutocompleteJsonView(AutocompleteJsonView):
    """
    Django's stock autocomplete, with result sets limited for module
    substitution FKs:

    - preferred_module → items on the fitting EFT
    - substitute_module → variants of preferred (or of all fit items)
    """

    def get_queryset(self):
        qs = self.model_admin.get_queryset(self.request)
        qs = self._scope_module_substitution(qs)
        qs = qs.complex_filter(self.source_field.get_limit_choices_to())
        qs, search_use_distinct = self.model_admin.get_search_results(
            self.request, qs, self.term
        )
        if search_use_distinct:
            qs = qs.distinct()
        return qs

    def _scope_module_substitution(self, qs):
        if self.source_field.model is not EveFittingModuleSubstitution:
            return qs
        if self.model_admin.model is not EveType:
            return qs

        fitting_id = self.request.GET.get("fitting_id") or ""
        fitting = (
            EveFitting.objects.filter(pk=fitting_id).first()
            if fitting_id
            else None
        )
        field_name = self.source_field.name

        if field_name == "preferred_module":
            if fitting is None:
                return EveType.objects.none()
            return fitting_item_types(fitting)

        if field_name == "substitute_module":
            preferred_id = self.request.GET.get("preferred_id") or ""
            if preferred_id:
                preferred = EveType.objects.filter(pk=preferred_id).first()
                if preferred is None:
                    return EveType.objects.none()
                return variant_types_for(preferred)
            if fitting is None:
                return EveType.objects.none()
            return variant_types_for_fitting_items(fitting_item_types(fitting))

        return qs
