from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from eveonline.models import EveLocation

from fittings.helpers.module_substitutions import (
    fitting_item_types,
    types_are_variants,
)

from .known_fitting import KnownFitting
from .models import (
    ChangeRequestStatus,
    EveDoctrine,
    EveDoctrineChangeRequest,
    EveDoctrineFitting,
    EveFitting,
    EveFittingChangeRequest,
    EveFittingModuleSubstitution,
    EveFittingRefit,
    FittingTag,
)


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
    known_key = forms.ChoiceField(
        choices=[("", "---------")] + list(KnownFitting.choices),
        required=False,
        help_text=(
            "Stable catalog key for guides and app features "
            "(e.g. guide.fw-cruiser.omen-kite-pulse). Not versioned with EFT."
        ),
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
        # tags is a slug MultipleChoiceField; M2M is applied via change requests.
        exclude = ("tags",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        raw = self.initial.get("aliases")
        if raw:
            self.initial["aliases"] = aliases_for_textarea(raw)
        if self.instance and self.instance.pk:
            self.initial["tags"] = self.instance.tag_slugs()
        if "eft_format" in self.fields:
            self.fields["eft_format"].help_text = (
                "Fitting name is taken from the EFT header "
                "([ShipName, Fitting name])."
            )

    def clean_aliases(self):
        return normalize_fitting_aliases(
            self.cleaned_data.get("aliases") or ""
        )

    def clean_known_key(self):
        value = self.cleaned_data.get("known_key") or ""
        return value or None

    def clean(self):
        cleaned = super().clean()
        eft = cleaned.get("eft_format") or ""
        derived = EveFitting.fitting_name_from_eft(eft)
        if eft.strip() and not derived:
            self.add_error(
                "eft_format",
                "EFT header must include a fitting name: "
                "[ShipName, Fitting name].",
            )
        elif derived:
            dupes = EveFitting.objects.filter(name=derived)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                self.add_error(
                    "eft_format",
                    f"A fitting named {derived!r} already exists.",
                )
            else:
                pending_create = (
                    EveFitting.all_objects.filter(
                        name=derived,
                        deleted__isnull=False,
                        change_requests__status=ChangeRequestStatus.PENDING,
                        change_requests__change_kind="fitting_create",
                    )
                    .exclude(pk=self.instance.pk or 0)
                    .exists()
                )
                if pending_create:
                    self.add_error(
                        "eft_format",
                        f"A pending create request already uses the name "
                        f"{derived!r}.",
                    )

        known_key = cleaned.get("known_key")
        if known_key:
            dupes = EveFitting.objects.filter(known_key=known_key)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                self.add_error(
                    "known_key",
                    f"known key {known_key!r} is already assigned to another "
                    f"fitting.",
                )
        return cleaned


class EveFittingRefitInlineForm(forms.ModelForm):
    """Derive refit name from EFT; name field is readonly in admin."""

    class Meta:
        model = EveFittingRefit
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        eft = cleaned.get("eft_format")
        if eft is None:
            eft = getattr(self.instance, "eft_format", "") or ""
        derived = EveFitting.fitting_name_from_eft(eft)
        if str(eft).strip() and not derived:
            self.add_error(
                "eft_format",
                "EFT header must include a fitting name: "
                "[ShipName, Fitting name].",
            )
        elif derived:
            cleaned["name"] = derived
            base = cleaned.get("base_fitting") or getattr(
                self.instance, "base_fitting", None
            )
            if base is not None:
                dupes = EveFittingRefit.objects.filter(
                    base_fitting=base, name=derived
                )
                if self.instance.pk:
                    dupes = dupes.exclude(pk=self.instance.pk)
                if dupes.exists():
                    self.add_error(
                        "eft_format",
                        f"A refit named {derived!r} already exists "
                        "for this fitting.",
                    )
        return cleaned


class EveFittingModuleSubstitutionInlineForm(forms.ModelForm):
    """Validate preferred is on the fit and substitute is a real variant."""

    class Meta:
        model = EveFittingModuleSubstitution
        fields = ("preferred_module", "substitute_module", "notes")

    def __init__(self, *args, fitting=None, **kwargs):
        super().__init__(*args, **kwargs)
        if fitting is None and getattr(self.instance, "fitting_id", None):
            fitting = self.instance.fitting
        self._fitting = fitting
        if "preferred_module" in self.fields:
            self.fields["preferred_module"].help_text = (
                "Only items present on this fitting’s EFT."
            )
        if "substitute_module" in self.fields:
            self.fields["substitute_module"].help_text = (
                "Meta / faction / T1–T2 variants of the preferred module."
            )

    def clean(self):
        cleaned = super().clean()
        preferred = cleaned.get("preferred_module")
        substitute = cleaned.get("substitute_module")
        fitting = self._fitting
        if fitting is not None and preferred is not None:
            allowed = set(
                fitting_item_types(fitting).values_list("pk", flat=True)
            )
            if preferred.pk not in allowed:
                self.add_error(
                    "preferred_module",
                    "Must be an item from this fitting’s EFT.",
                )
        if preferred is not None and substitute is not None:
            if preferred.pk == substitute.pk:
                self.add_error(
                    "substitute_module",
                    "Substitute must differ from the preferred module.",
                )
            elif not types_are_variants(preferred, substitute):
                self.add_error(
                    "substitute_module",
                    "Must be a variant of the preferred module.",
                )
        return cleaned


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


class ChangeRequestReviewForm(forms.ModelForm):
    REVIEW_ACTION_NONE = ""
    REVIEW_ACTION_APPROVE = "approve"
    REVIEW_ACTION_REJECT = "reject"
    REVIEW_ACTION_CANCEL = "cancel"

    review_action = forms.ChoiceField(
        label="Review action",
        required=False,
        choices=[(REVIEW_ACTION_NONE, "— No action —")],
        help_text="Choose an action, then click Save.",
        widget=forms.Select(attrs={"style": "min-width:16em;"}),
    )

    class Meta:
        fields = []


class EveDoctrineChangeRequestAdminForm(ChangeRequestReviewForm):
    class Meta(ChangeRequestReviewForm.Meta):
        model = EveDoctrineChangeRequest


class EveFittingChangeRequestAdminForm(ChangeRequestReviewForm):
    class Meta(ChangeRequestReviewForm.Meta):
        model = EveFittingChangeRequest
