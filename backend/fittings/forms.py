from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from eveonline.models import EveLocation

from .models import EveDoctrine, EveDoctrineFitting, EveFitting, FittingTag


def normalize_fitting_aliases(raw: str) -> str:
    """Collapse newlines and commas into a single comma+space separated string."""
    if not raw or not str(raw).strip():
        return ""
    parts: list[str] = []
    for chunk in (
        str(raw)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", ",")
        .split(",")
    ):
        t = chunk.strip()
        if t:
            parts.append(t)
    return ", ".join(parts)


def aliases_for_textarea(stored: str | None) -> str:
    """Show stored comma-separated aliases as one per line in the admin textarea."""
    if not stored or not str(stored).strip():
        return ""
    return "\n".join(p.strip() for p in str(stored).split(",") if p.strip())


class EveFittingAdminForm(forms.ModelForm):
    tags = forms.MultipleChoiceField(
        choices=FittingTag.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    aliases = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "cols": 80,
                "class": "vLargeTextField",
                "placeholder": "[FL33T] Tornado\n[NVY-30] Tornado",
            }
        ),
        help_text=(
            "Optional names that match item exchange contract titles (besides the "
            "EFT name). Put one per line, or separate with commas—spaces are trimmed "
            "when you save."
        ),
    )

    class Meta:
        model = EveFitting
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        raw = self.initial.get("aliases")
        if raw:
            self.initial["aliases"] = aliases_for_textarea(raw)

    def clean_aliases(self):
        return normalize_fitting_aliases(
            self.cleaned_data.get("aliases") or ""
        )


class EveDoctrineForm(forms.ModelForm):
    """
    Custom override form for django admin
    """

    name = forms.CharField(max_length=255)
    type = forms.ChoiceField(
        choices=EveDoctrine.type_choices,
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
    locations = forms.ModelMultipleChoiceField(
        queryset=EveLocation.objects.all(),
        widget=FilteredSelectMultiple("Locations", is_stacked=False),
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
            self.fields["locations"].initial = self.instance.locations.all()

    class Meta:
        model = EveDoctrine
        fields = [
            "name",
            "type",
            "description",
        ]
