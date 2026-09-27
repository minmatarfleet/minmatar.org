"""Admin / API forms for campaign theaters (systems, constellations, regions)."""

from __future__ import annotations

from django import forms
from django.conf import settings

from campaigns.constants import CAMPAIGN_COVER_CHOICES, CAMPAIGN_COVER_PATHS
from campaigns.models import (
    AreaScope,
    CampaignArea,
    CampaignSystem,
    SystemPriority,
    SystemRole,
)


class CoverImageRadioSelect(forms.RadioSelect):
    """Radio grid with thumbnails for curated campaign covers."""

    template_name = "admin/campaigns/widgets/cover_radio.html"
    option_template_name = "admin/campaigns/widgets/cover_radio_option.html"

    class Media:
        css = {"all": ("campaigns/admin_cover_picker.css",)}

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        path = "" if value in (None, "") else str(value)
        base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org")
        option["cover_url"] = f"{base.rstrip('/')}{path}" if path else ""
        return option


def cover_image_formfield(*, current_value: str = ""):
    """Choice field for Story / add forms; keeps legacy custom URLs selectable."""
    choices = list(CAMPAIGN_COVER_CHOICES)
    value = (current_value or "").strip()
    if value and value not in CAMPAIGN_COVER_PATHS and value != "":
        choices.append((value, f"Custom (legacy): {value}"))
    return forms.ChoiceField(
        choices=choices,
        required=False,
        label="Cover",
        widget=CoverImageRadioSelect,
        help_text=(
            "Site gallery covers. Default uses the kind fallback on the "
            "campaign card."
        ),
    )


# Scoring still keys off role (primary-system fleet/site bonuses). Operators
# only set Priority; we keep role in sync so those bonuses stay meaningful.
PRIORITY_TO_ROLE = {
    SystemPriority.HIGH: SystemRole.PRIMARY,
    SystemPriority.MEDIUM: SystemRole.SECONDARY,
    SystemPriority.LOW: SystemRole.SUPPORT,
}


class CampaignSystemTheaterForm(forms.ModelForm):
    """Add a system theater via EveSolarSystem type-ahead."""

    class Meta:
        model = CampaignSystem
        fields = (
            "eve_solar_system",
            "is_fw_objective",
            "goal",
            "priority",
            "retired_at",
        )

    def clean(self):
        cleaned = super().clean()
        system = cleaned.get("eve_solar_system")
        if system is None and not self.instance.pk:
            raise forms.ValidationError("Pick a solar system.")
        priority = cleaned.get("priority") or SystemPriority.MEDIUM
        cleaned["role"] = PRIORITY_TO_ROLE.get(priority, SystemRole.SECONDARY)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.sync_from_eve_solar_system()
        if not instance.solar_system_id and instance.pk:
            # Editing without changing the lookup keeps existing ids.
            pass
        elif not instance.solar_system_id:
            raise forms.ValidationError("Pick a solar system.")
        instance.role = PRIORITY_TO_ROLE.get(
            instance.priority, SystemRole.SECONDARY
        )
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CampaignConstellationTheaterForm(forms.ModelForm):
    """Add a constellation theater via EveConstellation type-ahead."""

    class Meta:
        model = CampaignArea
        fields = ("eve_constellation", "goal", "priority")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("eve_constellation") is None and not self.instance.pk:
            raise forms.ValidationError("Pick a constellation.")
        cleaned["scope"] = AreaScope.CONSTELLATION
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.scope = AreaScope.CONSTELLATION
        instance.sync_from_eve_lookups()
        if not instance.constellation_id:
            raise forms.ValidationError("Pick a constellation.")
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CampaignRegionTheaterForm(forms.ModelForm):
    """Add a region theater via EveRegion type-ahead."""

    class Meta:
        model = CampaignArea
        fields = ("eve_region", "goal", "priority")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("eve_region") is None and not self.instance.pk:
            raise forms.ValidationError("Pick a region.")
        cleaned["scope"] = AreaScope.REGION
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.scope = AreaScope.REGION
        instance.sync_from_eve_lookups()
        if not instance.region_id:
            raise forms.ValidationError("Pick a region.")
        if commit:
            instance.save()
            self.save_m2m()
        return instance
