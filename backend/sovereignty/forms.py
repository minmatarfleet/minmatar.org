import requests
from django import forms
from django.core.exceptions import ValidationError
from eveuniverse.models import EveSolarSystem

from sovereignty.models import SystemSovereigntyConfig


def resolve_system_id(value: str) -> int:
    """
    Resolve system ID from either a numeric ID or a system name (Eve universe).
    Raises ValidationError if name is not found or value is invalid.
    """
    if not value or not str(value).strip():
        raise ValidationError("Enter a system ID or system name.")
    value = str(value).strip()
    if value.isdigit():
        return int(value)

    solar_system = EveSolarSystem.objects.filter(name__iexact=value).first()
    if solar_system is None:
        # Try loading from ESI in case it's not in DB yet
        try:
            resp = requests.get(
                "https://esi.evetech.net/latest/search/",
                params={"categories": "solar_system", "search": value},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            system_ids = data.get("solar_system")
            if not system_ids:
                raise ValidationError(
                    f"No solar system found with name “{value}”. "
                    "Check spelling or use a system ID."
                )
            system_id = system_ids[0]
            EveSolarSystem.objects.get_or_create_esi(id=system_id)
            return system_id
        except (requests.RequestException, KeyError, IndexError) as exc:
            raise ValidationError(
                f"No solar system found with name “{value}”. "
                "Check spelling or use a system ID."
            ) from exc
    return solar_system.id


class SystemSovereigntyConfigAdminForm(forms.ModelForm):
    """Accepts system as ID or name; resolves name to ID from Eve universe."""

    system = forms.CharField(
        label="System (ID or name)",
        max_length=255,
        required=True,
        help_text="Enter a system ID (e.g. 30000142) or system name (e.g. Jita). Name is resolved from the Eve universe.",
    )

    class Meta:
        model = SystemSovereigntyConfig
        fields = (
            []
        )  # system_id set in save(); system_name resolved from universe
        field_order = ["system"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.system_id:
            # Show current system name or ID when editing
            self.initial["system"] = self.instance.system_name or str(
                self.instance.system_id
            )

    def clean_system(self):
        value = self.cleaned_data.get("system")
        return resolve_system_id(value)

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.system_id = self.cleaned_data["system"]
        if commit:
            obj.save()
        return obj
