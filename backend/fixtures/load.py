"""Load helpers for reference fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth.models import Group
from django.core.management import call_command

from eveonline.models import EveLocation
from fittings.models import (
    EveDoctrine,
    EveDoctrineFitting,
    EveDoctrineHistory,
    EveFitting,
    EveFittingHistory,
    EveFittingRefit,
)
from fleets.models import EveFleetAudience
from groups.models import AffiliationType
from industry.models import IndustryProduct
from market.models import (
    EveMarketContractExpectation,
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
)
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupActivity,
    TribeGroupRequirement,
    TribeGroupRequirementAssetType,
    TribeGroupRequirementSkill,
)

from fixtures.export import FIXTURE_FILES


def clear_reference_data() -> dict[str, int]:
    """Delete reference rows in reverse dependency order. Returns model → count."""
    deleted: dict[str, int] = {}

    def _delete(label, qs):
        count, _ = qs.all().delete()
        deleted[label] = count
        return count

    _delete("IndustryProduct", IndustryProduct.objects)
    _delete(
        "EveMarketContractExpectation", EveMarketContractExpectation.objects
    )
    _delete("EveMarketFittingExpectation", EveMarketFittingExpectation.objects)
    _delete("EveMarketItemExpectation", EveMarketItemExpectation.objects)
    _delete("EveFleetAudience", EveFleetAudience.objects)
    _delete("TribeGroupActivity", TribeGroupActivity.objects)
    _delete("TribeGroupRequirementSkill", TribeGroupRequirementSkill.objects)
    _delete(
        "TribeGroupRequirementAssetType",
        TribeGroupRequirementAssetType.objects,
    )
    _delete("TribeGroupRequirement", TribeGroupRequirement.objects)
    _delete("TribeGroup", TribeGroup.objects)
    _delete("Tribe", Tribe.objects)
    _delete("EveDoctrineHistory", EveDoctrineHistory.objects)
    _delete("EveDoctrineFitting", EveDoctrineFitting.objects)
    _delete("EveDoctrine", EveDoctrine.objects)
    _delete("EveFittingHistory", EveFittingHistory.objects)
    _delete("EveFittingRefit", EveFittingRefit.objects)
    _delete("EveFitting", EveFitting.all_objects)
    _delete("AffiliationType", AffiliationType.objects)
    _delete("EveLocation", EveLocation.all_objects)
    _delete("auth.Group", Group.objects)

    return deleted


def load_fixture_dir(fixture_dir: Path, *, stdout=None) -> None:
    """Load fixture files in dependency order via loaddata."""
    for filename in FIXTURE_FILES:
        path = fixture_dir / filename
        if not path.exists():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not rows:
            continue
        if stdout:
            stdout.write(f"  Loading {filename}…")
        call_command("loaddata", str(path), verbosity=0)
