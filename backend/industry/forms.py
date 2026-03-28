"""Forms for industry admin."""

from django import forms
from django.utils import timezone

from industry.helpers.public_short_code import (
    is_valid_public_short_code,
    pick_unique_public_short_code_among_actives,
    public_short_code_taken_by_active,
)
from industry.models import IndustryOrder, MiningUpgradeCompletion
from sovereignty.anomalies import get_all_mining_anomaly_names


class MiningUpgradeCompletionAdminForm(forms.ModelForm):
    """Admin form: sov system + anomaly (all mining anomalies; validated against system on save)."""

    class Meta:
        model = MiningUpgradeCompletion
        fields = ("sov_system", "site_name", "completed_at", "completed_by")

    site_name = forms.ChoiceField(
        choices=[],  # set in __init__
        required=False,
        label="Anomaly",
        help_text="Mining anomaly. Must be one available in the selected sov system.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sov_system"].required = True
        all_anomalies = get_all_mining_anomaly_names()
        self.fields["site_name"].choices = [("", "---------")] + [
            (name, name) for name in all_anomalies
        ]
        if not kwargs.get("instance") or not kwargs["instance"].pk:
            self.fields["completed_at"].initial = timezone.now()

    def clean(self):
        cleaned = super().clean()
        sov_system = cleaned.get("sov_system")
        site_name = (cleaned.get("site_name") or "").strip()
        if not sov_system or not site_name:
            return cleaned
        available = [name for name, _ in sov_system.get_anomalies()]
        if site_name not in set(available):
            system_label = sov_system.system_name or str(sov_system.system_id)
            available_list = (
                ", ".join(sorted(available)) if available else "(none)"
            )
            self.add_error(
                "site_name",
                forms.ValidationError(
                    f"“{site_name}” is not available in {system_label}. "
                    f"Available in this system: {available_list}.",
                ),
            )
        return cleaned


class IndustryOrderAdminForm(forms.ModelForm):
    """Show ``public_short_code`` as read-only; validated in ``clean_public_short_code``."""

    class Meta:
        model = IndustryOrder
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["public_short_code"]
        field.widget.attrs["readonly"] = True
        field.required = False
        inst = self.instance
        if inst.pk and inst.public_short_code:
            field.initial = inst.public_short_code
        elif not inst.pk:
            field.initial = pick_unique_public_short_code_among_actives()

    def clean_public_short_code(self):
        raw = (self.data.get("public_short_code") or "").strip()
        if self.instance.pk:
            return self.instance.public_short_code
        if is_valid_public_short_code(
            raw
        ) and not public_short_code_taken_by_active(
            raw, exclude_order_pk=None
        ):
            return raw
        return pick_unique_public_short_code_among_actives()
