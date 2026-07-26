"""
Export non-sensitive reference data from production_readonly as Django JSON fixtures.

Read-only against the source DB alias; never writes to production_readonly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from django.contrib.auth.models import Group
from django.core.serializers import serialize

from eveonline.models import EveLocation
from eveuniverse.models import EveType
from fittings.models import (
    EveDoctrine,
    EveDoctrineFitting,
    EveDoctrineHistory,
)
from fleets.models import EveFleetAudience
from groups.models import AffiliationType
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

FIXTURE_FILES = (
    "01_auth_groups.json",
    "02_eve_locations.json",
    "03_affiliation_types.json",
    "05_doctrines.json",
    "06_tribes.json",
    "07_fleet_audiences.json",
    "08_market_expectations.json",
    "10_help_tickets.json",
)

SANITIZE_FIELDS: dict[str, set[str]] = {
    "tribes.tribe": {"discord_channel_id", "chief", "group"},
    "tribes.tribegroup": {"discord_channel_id", "chief", "group"},
    "fleets.evefleetaudience": {
        "discord_channel_id",
        "discord_channel_name",
    },
}

SANITIZE_EMPTY_LISTS: dict[str, set[str]] = {
    "fleets.evefleetaudience": {"groups"},
}


@dataclass
class ExportBundle:
    auth_groups: list[Group] = field(default_factory=list)
    eve_locations: list[EveLocation] = field(default_factory=list)
    affiliation_types: list[AffiliationType] = field(default_factory=list)
    doctrines: list[EveDoctrine] = field(default_factory=list)
    doctrine_fittings: list[EveDoctrineFitting] = field(default_factory=list)
    doctrine_history: list[EveDoctrineHistory] = field(default_factory=list)
    tribes: list[Tribe] = field(default_factory=list)
    tribe_groups: list[TribeGroup] = field(default_factory=list)
    tribe_requirements: list[TribeGroupRequirement] = field(
        default_factory=list
    )
    tribe_requirement_skills: list[TribeGroupRequirementSkill] = field(
        default_factory=list
    )
    tribe_requirement_asset_types: list[TribeGroupRequirementAssetType] = (
        field(default_factory=list)
    )
    tribe_activities: list[TribeGroupActivity] = field(default_factory=list)
    fleet_audiences: list[EveFleetAudience] = field(default_factory=list)
    market_item_expectations: list[EveMarketItemExpectation] = field(
        default_factory=list
    )
    market_fitting_expectations: list[EveMarketFittingExpectation] = field(
        default_factory=list
    )
    market_contract_expectations: list[EveMarketContractExpectation] = field(
        default_factory=list
    )


def collect_reference_data(
    source_db: str, *, include_history: bool = False
) -> ExportBundle:
    """Read reference rows from *source_db* (e.g. production_readonly)."""
    bundle = ExportBundle()

    tribes = list(
        Tribe.objects.using(source_db)
        .select_related("group", "chief")
        .order_by("pk")
    )
    tribe_groups = list(
        TribeGroup.objects.using(source_db)
        .select_related("tribe", "group", "chief")
        .order_by("pk")
    )
    affiliation_types = list(
        AffiliationType.objects.using(source_db)
        .select_related("group")
        .order_by("pk")
    )

    group_ids: set[int] = set()
    for tribe in tribes:
        if tribe.group_id:
            group_ids.add(tribe.group_id)
    for tg in tribe_groups:
        if tg.group_id:
            group_ids.add(tg.group_id)
    for aff in affiliation_types:
        if aff.group_id:
            group_ids.add(aff.group_id)

    bundle.auth_groups = list(
        Group.objects.using(source_db).filter(pk__in=group_ids).order_by("pk")
    )
    bundle.eve_locations = list(
        EveLocation.objects.using(source_db).order_by("location_id")
    )
    bundle.affiliation_types = affiliation_types

    # Fittings / refits / fitting history are intentionally not exported.
    # Fixture load must not wipe or replace live doctrine fits.

    bundle.doctrines = list(
        EveDoctrine.objects.using(source_db)
        .prefetch_related("locations")
        .order_by("pk")
    )
    doctrine_pks = [d.pk for d in bundle.doctrines]
    bundle.doctrine_fittings = list(
        EveDoctrineFitting.objects.using(source_db)
        .filter(doctrine_id__in=doctrine_pks)
        .order_by("pk")
    )
    if include_history:
        bundle.doctrine_history = list(
            EveDoctrineHistory.objects.using(source_db)
            .filter(doctrine_id__in=doctrine_pks)
            .order_by("pk")
        )

    bundle.tribes = tribes
    bundle.tribe_groups = tribe_groups
    tribe_group_pks = [tg.pk for tg in bundle.tribe_groups]
    bundle.tribe_requirements = list(
        TribeGroupRequirement.objects.using(source_db)
        .filter(tribe_group_id__in=tribe_group_pks)
        .order_by("pk")
    )
    req_pks = [r.pk for r in bundle.tribe_requirements]
    bundle.tribe_requirement_skills = list(
        TribeGroupRequirementSkill.objects.using(source_db)
        .filter(requirement_id__in=req_pks)
        .order_by("pk")
    )
    asset_type_qs = (
        TribeGroupRequirementAssetType.objects.using(source_db)
        .filter(requirement_id__in=req_pks)
        .prefetch_related("locations")
        .order_by("pk")
    )
    bundle.tribe_requirement_asset_types = list(asset_type_qs)
    bundle.tribe_activities = list(
        TribeGroupActivity.objects.using(source_db)
        .filter(tribe_group_id__in=tribe_group_pks)
        .order_by("pk")
    )

    bundle.fleet_audiences = list(
        EveFleetAudience.objects.using(source_db)
        .select_related("staging_location")
        .prefetch_related("groups")
        .order_by("pk")
    )

    bundle.market_item_expectations = list(
        EveMarketItemExpectation.objects.using(source_db)
        .select_related("item", "location")
        .order_by("pk")
    )
    bundle.market_fitting_expectations = list(
        EveMarketFittingExpectation.objects.using(source_db)
        .select_related("fitting", "location")
        .order_by("pk")
    )
    bundle.market_contract_expectations = list(
        EveMarketContractExpectation.objects.using(source_db)
        .select_related("fitting", "location")
        .order_by("pk")
    )

    return bundle


def bundle_counts(bundle: ExportBundle) -> dict[str, int]:
    """Return row counts per fixture section for dry-run reporting."""
    return {
        "auth.Group": len(bundle.auth_groups),
        "eveonline.EveLocation": len(bundle.eve_locations),
        "groups.AffiliationType": len(bundle.affiliation_types),
        "fittings.EveDoctrine": len(bundle.doctrines),
        "fittings.EveDoctrineFitting": len(bundle.doctrine_fittings),
        "fittings.EveDoctrineHistory": len(bundle.doctrine_history),
        "tribes.Tribe": len(bundle.tribes),
        "tribes.TribeGroup": len(bundle.tribe_groups),
        "tribes.TribeGroupRequirement": len(bundle.tribe_requirements),
        "tribes.TribeGroupRequirementSkill": len(
            bundle.tribe_requirement_skills
        ),
        "tribes.TribeGroupRequirementAssetType": len(
            bundle.tribe_requirement_asset_types
        ),
        "tribes.TribeGroupActivity": len(bundle.tribe_activities),
        "fleets.EveFleetAudience": len(bundle.fleet_audiences),
        "market.EveMarketItemExpectation": len(
            bundle.market_item_expectations
        ),
        "market.EveMarketFittingExpectation": len(
            bundle.market_fitting_expectations
        ),
        "market.EveMarketContractExpectation": len(
            bundle.market_contract_expectations
        ),
    }


def collect_eve_type_ids(bundle: ExportBundle) -> set[int]:
    """EveType PKs referenced by exported rows."""
    type_ids: set[int] = set()
    for row in bundle.tribe_requirement_skills:
        if row.eve_type_id:
            type_ids.add(row.eve_type_id)
    for row in bundle.tribe_requirement_asset_types:
        if row.eve_type_id:
            type_ids.add(row.eve_type_id)
    for row in bundle.market_item_expectations:
        if row.item_id:
            type_ids.add(row.item_id)
    return type_ids


def missing_eve_type_ids(
    type_ids: Iterable[int], db: str = "default"
) -> list[int]:
    """Return sorted EveType PKs missing from *db*."""
    ids = set(type_ids)
    if not ids:
        return []
    present = set(
        EveType.objects.using(db)
        .filter(pk__in=ids)
        .values_list("pk", flat=True)
    )
    return sorted(ids - present)


def _serialize_queryset(objects: list) -> list[dict]:
    if not objects:
        return []
    raw = serialize("json", objects, use_natural_foreign_keys=False)
    return json.loads(raw)


def _apply_sanitization(objects: list[dict]) -> list[dict]:
    for obj in objects:
        fields_to_clear = SANITIZE_FIELDS.get(obj["model"])
        if not fields_to_clear:
            continue
        for field_name in fields_to_clear:
            if field_name in obj["fields"]:
                obj["fields"][field_name] = None
        for field_name in SANITIZE_EMPTY_LISTS.get(obj["model"], ()):
            if field_name in obj["fields"]:
                obj["fields"][field_name] = []
    return objects


def serialize_bundle(bundle: ExportBundle) -> dict[str, list[dict]]:
    """Return fixture dicts keyed by output filename."""
    doctrines_objects = (
        list(bundle.doctrines)
        + list(bundle.doctrine_fittings)
        + list(bundle.doctrine_history)
    )
    tribes_objects = (
        list(bundle.tribes)
        + list(bundle.tribe_groups)
        + list(bundle.tribe_requirements)
        + list(bundle.tribe_requirement_skills)
        + list(bundle.tribe_requirement_asset_types)
        + list(bundle.tribe_activities)
    )
    market_objects = (
        list(bundle.market_item_expectations)
        + list(bundle.market_fitting_expectations)
        + list(bundle.market_contract_expectations)
    )

    return {
        "01_auth_groups.json": _serialize_queryset(bundle.auth_groups),
        "02_eve_locations.json": _serialize_queryset(bundle.eve_locations),
        "03_affiliation_types.json": _serialize_queryset(
            bundle.affiliation_types
        ),
        "05_doctrines.json": _serialize_queryset(doctrines_objects),
        "06_tribes.json": _apply_sanitization(
            _serialize_queryset(tribes_objects)
        ),
        "07_fleet_audiences.json": _apply_sanitization(
            _serialize_queryset(bundle.fleet_audiences)
        ),
        "08_market_expectations.json": _serialize_queryset(market_objects),
    }


def write_fixture_files(
    bundle: ExportBundle, output_dir, *, indent: int = 2
) -> dict[str, int]:
    """Write split JSON fixture files; return filename → row count."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    serialized = serialize_bundle(bundle)
    written: dict[str, int] = {}
    for filename, rows in serialized.items():
        path = out / filename
        path.write_text(
            json.dumps(rows, indent=indent) + "\n",
            encoding="utf-8",
        )
        written[filename] = len(rows)
    return written
