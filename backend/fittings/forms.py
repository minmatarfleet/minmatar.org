from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from .models import EveDoctrine, EveDoctrineFitting, EveFitting


class EveDoctrineForm(forms.ModelForm):
    """
    Custom override form for django admin
    """

    name = forms.CharField(max_length=255)
    type = forms.ChoiceField(
        choices=(
            ("armor", "Armor"),
            ("shield", "Shield"),
            ("kitchen_sink", "Kitchen Sink"),
        )
    )
    description = forms.CharField(widget=forms.Textarea)
    primary_fittings = forms.ModelMultipleChoiceField(
        queryset=EveFitting.objects.all(),
        widget=FilteredSelectMultiple("Primary Fittings", is_stacked=False),
        required=False,
    )
    secondary_fittings = forms.ModelMultipleChoiceField(
        queryset=EveFitting.objects.all(),
        widget=FilteredSelectMultiple("Secondary Fittings", is_stacked=False),
        required=False,
    )
    support_fittings = forms.ModelMultipleChoiceField(
        queryset=EveFitting.objects.all(),
        widget=FilteredSelectMultiple("Support Fittings", is_stacked=False),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            doctrine_id = self.instance.id
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
            self.fields["primary_fittings"].initial = primary_doctrine_fittings
            self.fields["secondary_fittings"].initial = (
                secondary_doctrine_fittings
            )
            self.fields["support_fittings"].initial = support_doctrine_fittings

    class Meta:
        model = EveDoctrine
        fields = [
            "name",
            "type",
            "description",
        ]
