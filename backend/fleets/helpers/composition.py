"""
Fleet composition: the set of ships a fleet expects, merged from the
doctrine (if any) and the fleet's own fittings (catalog picks or manual EFT).
"""

from dataclasses import dataclass, field

from eveuniverse.models import EveType
from fittings.models import EveDoctrineFitting, EveFitting

from fleets.helpers.eft_items import eft_item_names, module_slots_for

ROLE_ORDER = {"primary": 0, "secondary": 1, "support": 2}


@dataclass
class CompositionEntry:
    """One ship in the fleet composition."""

    name: str
    ship_id: int
    role: str
    source: str  # doctrine | catalog | manual
    eft_format: str = ""
    fitting_id: int | None = None
    fleet_fitting_id: int | None = None
    ship_name: str = ""
    ship_group: str = ""  # EveGroup name, e.g. "Dreadnought"
    # module name -> "high" | "mid" | "low" | "rig" for every module named in
    # the EFT (fitted or in cargo); lets the UI offer slot-compatible swaps.
    module_slots: dict = field(default_factory=dict)
    refits: list = field(default_factory=list)  # [(id, name)]

    @property
    def key(self) -> str:
        """Catalog fits key on the EveFitting (shared with doctrine entries)."""
        if self.fitting_id:
            return f"f:{self.fitting_id}"
        return f"m:{self.fleet_fitting_id}"


def ship_id_for_eft(eft_format: str) -> int | None:
    """Resolve the hull type id from an EFT header via the universe cache."""
    ship_name = EveFitting.ship_name_from_eft(eft_format or "")
    if not ship_name:
        return None
    eve_type = EveType.objects.filter(name__iexact=ship_name).first()
    return eve_type.id if eve_type else None


def fleet_composition(eve_fleet) -> list[CompositionEntry]:
    """Doctrine fits first (by role), then fleet fittings (by role, order)."""
    # Imported here: fleets.models imports this module's siblings.
    from fleets.models import (  # pylint: disable=import-outside-toplevel
        EveFleetFitting,
    )

    entries: list[CompositionEntry] = []
    if eve_fleet.doctrine_id:
        doctrine_fittings = (
            EveDoctrineFitting.objects.filter(
                doctrine_id=eve_fleet.doctrine_id
            )
            .select_related("fitting")
            .prefetch_related("fitting__refits")
        )
        for doctrine_fitting in sorted(
            doctrine_fittings,
            key=lambda df: (ROLE_ORDER.get(df.role, 9), df.fitting.name),
        ):
            fitting = doctrine_fitting.fitting
            entries.append(
                CompositionEntry(
                    name=fitting.name,
                    ship_id=fitting.ship_id,
                    role=doctrine_fitting.role,
                    source="doctrine",
                    eft_format=fitting.eft_format,
                    fitting_id=fitting.id,
                    refits=[(r.id, r.name) for r in fitting.refits.all()],
                )
            )

    seen_catalog = {e.fitting_id for e in entries if e.fitting_id}
    fleet_fittings = (
        EveFleetFitting.objects.filter(eve_fleet=eve_fleet)
        .select_related("fitting")
        .prefetch_related("fitting__refits")
        .order_by("order", "id")
    )
    for fleet_fitting in sorted(
        fleet_fittings,
        key=lambda ff: (ROLE_ORDER.get(ff.role, 9), ff.order, ff.id),
    ):
        if fleet_fitting.fitting_id:
            # Skip doctrine duplicates and (MySQL cannot enforce the
            # conditional unique constraint) repeated catalog picks.
            if fleet_fitting.fitting_id in seen_catalog:
                continue
            seen_catalog.add(fleet_fitting.fitting_id)
            fitting = fleet_fitting.fitting
            entries.append(
                CompositionEntry(
                    name=fitting.name,
                    ship_id=fitting.ship_id,
                    role=fleet_fitting.role,
                    source="catalog",
                    eft_format=fitting.eft_format,
                    fitting_id=fitting.id,
                    fleet_fitting_id=fleet_fitting.id,
                    refits=[(r.id, r.name) for r in fitting.refits.all()],
                )
            )
        else:
            entries.append(
                CompositionEntry(
                    name=fleet_fitting.name,
                    ship_id=fleet_fitting.ship_id,
                    role=fleet_fitting.role,
                    source="manual",
                    eft_format=fleet_fitting.eft_format,
                    fleet_fitting_id=fleet_fitting.id,
                )
            )

    hulls = {
        type_id: (name, group_name or "")
        for type_id, name, group_name in EveType.objects.filter(
            id__in={e.ship_id for e in entries}
        ).values_list("id", "name", "eve_group__name")
    }
    for entry in entries:
        name, group_name = hulls.get(entry.ship_id, ("", ""))
        entry.ship_name = name or (
            EveFitting.ship_name_from_eft(entry.eft_format)
            if entry.eft_format
            else ""
        )
        entry.ship_group = group_name

    names_by_entry = {
        entry.key: eft_item_names(entry.eft_format) for entry in entries
    }
    all_slots = module_slots_for(set().union(*names_by_entry.values()))
    for entry in entries:
        entry.module_slots = {
            name: all_slots[name]
            for name in names_by_entry[entry.key]
            if name in all_slots
        }

    return entries


def composition_catalog_fitting_ids(eve_fleet) -> set[int]:
    """Catalog fitting ids usable for volunteers/refits on this fleet."""
    return {
        entry.fitting_id
        for entry in fleet_composition(eve_fleet)
        if entry.fitting_id
    }


def resolve_composition_target(
    eve_fleet, fitting_id: int | None, fleet_fitting_id: int | None
):
    """
    Return (fitting, fleet_fitting, error). Exactly one id must be given;
    the target must be part of the fleet's composition. Catalog fleet
    fittings resolve to their EveFitting so refits/volunteers key on the
    catalog fit regardless of whether it came from the doctrine.
    """
    from fleets.models import (  # pylint: disable=import-outside-toplevel
        EveFleetFitting,
    )

    if bool(fitting_id) == bool(fleet_fitting_id):
        return (
            None,
            None,
            "Provide exactly one of fitting_id or fleet_fitting_id",
        )

    if fleet_fitting_id:
        fleet_fitting = EveFleetFitting.objects.filter(
            id=fleet_fitting_id, eve_fleet=eve_fleet
        ).first()
        if not fleet_fitting:
            return None, None, "Fleet fitting not found"
        if fleet_fitting.fitting_id:
            return fleet_fitting.fitting, None, None
        return None, fleet_fitting, None

    if fitting_id not in composition_catalog_fitting_ids(eve_fleet):
        if (
            not eve_fleet.doctrine_id
            and not EveFleetFitting.objects.filter(
                eve_fleet=eve_fleet
            ).exists()
        ):
            return (
                None,
                None,
                "Fleet has no doctrine or fittings; set one before configuring ships",
            )
        return None, None, "Fitting is not part of this fleet's composition"
    fitting = EveFitting.objects.filter(id=fitting_id).first()
    if not fitting:
        return None, None, "Fitting not found"
    return fitting, None, None
