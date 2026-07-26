"""
Convert a leaf BOM into compressed highsec belt/moon ore at a facility refine rate.

Examples:

    # From a build plan's leaf materials (refine rate from facility Tatara + rigs)
    pipenv run python manage.py plan_compressed_ore --from-plan Typhoon \\
      --quantity 10 --me 10 --te 20 --facility amamake

    # Override refine rate explicitly
    pipenv run python manage.py plan_compressed_ore \\
      --materials '{"Tritanium": 8000000, "Hydrocarbons": 9200}' \\
      --facility amamake --refine-rate 0.84
"""

from __future__ import annotations

import json
from typing import Dict, Optional

from django.core.management.base import BaseCommand, CommandError

from industry.helpers.build_planner import plan_build
from industry.helpers.compressed_ore import build_compressed_ore_plan
from industry.helpers.facility_profiles import (
    get_facility_refine_rate,
    get_facility_reprocessing_tax,
)

_MINERAL_SUMMARY_NAMES = (
    "Tritanium",
    "Pyerite",
    "Mexallon",
    "Isogen",
    "Nocxium",
    "Zydrine",
    "Megacyte",
    "Morphite",
)


def _write_named_qty_section(
    stdout, style, title: str, bucket: Dict[str, int]
):
    if not bucket:
        return
    stdout.write(style.MIGRATE_HEADING(title))
    for name, qty in sorted(bucket.items()):
        stdout.write(f"  {name}\t{qty:,}")


def _write_moon_ore_section(stdout, style, plan):
    if not plan.moon_ore_compressed:
        return
    stdout.write(style.MIGRATE_HEADING("Compressed moon ore"))
    for name, qty in sorted(plan.moon_ore_compressed.items()):
        stdout.write(f"  {name}\t{qty:,}")
    if not plan.moon_mineral_byproducts:
        return
    stdout.write("  (mineral byproducts credited)")
    for name, qty in sorted(plan.moon_mineral_byproducts.items()):
        if qty:
            stdout.write(f"    {name}\t{qty:,}")


def _write_mineral_balance_section(stdout, style, plan):
    if not plan.expected_minerals:
        return
    stdout.write("")
    stdout.write(style.MIGRATE_HEADING("Expected refine output vs needs"))
    for name in _MINERAL_SUMMARY_NAMES:
        need = plan.mineral_needs.get(name, 0)
        got = plan.expected_minerals.get(name, 0)
        bought = plan.mineral_imports.get(name, 0)
        if not (need or got or bought):
            continue
        delta = got + bought - need
        stdout.write(
            f"  {name}\tneed={need:,}\tfrom_ore={got:,}\t"
            f"import={bought:,}\tdelta={delta:+,}"
        )


class Command(BaseCommand):
    help = (
        "Convert leaf minerals/PI into compressed highsec belt and moon ore "
        "using the facility Tatara reprocessing yield (structure + Monitor "
        "rig + default skills V)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--materials",
            default=None,
            help="JSON object of material name -> quantity, e.g. '{\"Tritanium\": 1000}'",
        )
        parser.add_argument(
            "--from-plan",
            default=None,
            metavar="PRODUCT",
            help="Product name or type id; leaf BOM comes from plan_build.",
        )
        parser.add_argument("--quantity", type=int, default=1)
        parser.add_argument("--me", default="10")
        parser.add_argument("--te", default="20")
        parser.add_argument("--facility", default="amamake")
        parser.add_argument(
            "--refine-rate",
            type=float,
            default=None,
            help=(
                "Optional override for reprocessing yield 0–1. "
                "Default: derived from --facility Tatara + L Reprocessing "
                "Monitor II + skills V."
            ),
        )
        parser.add_argument(
            "--no-moon-ore",
            action="store_true",
            help="Do not convert PI P0 into compressed moon ore.",
        )
        parser.add_argument(
            "--format",
            choices=("summary", "tsv", "json"),
            default="summary",
            dest="output_format",
        )
        parser.add_argument(
            "--index-override",
            default=None,
            help="For --from-plan: manufacturing,reaction indexes (offline).",
        )

    def handle(self, *args, **options):
        facility = options["facility"]
        refine_override = options["refine_rate"]
        try:
            reprocessing_tax = get_facility_reprocessing_tax(facility)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if refine_override is not None:
            refine = float(refine_override)
            if refine <= 0 or refine > 1.0:
                raise CommandError("refine-rate must be in (0, 1]")
            rate_source = "override"
        else:
            try:
                refine = get_facility_refine_rate(facility)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            rate_source = facility

        materials = self._load_materials(options)
        plan = build_compressed_ore_plan(
            materials,
            refine_rate=refine,
            use_moon_ore=not options["no_moon_ore"],
            reprocessing_tax=reprocessing_tax,
        )

        fmt = options["output_format"]
        if fmt == "tsv":
            self.stdout.write(plan.tsv())
        elif fmt == "json":
            self.stdout.write(
                json.dumps(
                    {
                        "facility": facility,
                        "refine_rate": plan.refine_rate,
                        "refine_rate_source": rate_source,
                        "reprocessing_tax": plan.reprocessing_tax,
                        "includes_compressed_ore": plan.includes_compressed_ore,
                        "moon_ore_compressed": plan.moon_ore_compressed,
                        "belt_ore_compressed": plan.belt_ore_compressed,
                        "ice_compressed": plan.ice_compressed,
                        "moon_mineral_byproducts": plan.moon_mineral_byproducts,
                        "mineral_imports": plan.mineral_imports,
                        "pi_other_imports": plan.pi_other_imports,
                        "ice_imports": plan.ice_imports,
                        "other_imports": plan.other_imports,
                        "expected_minerals": plan.expected_minerals,
                        "expected_ice_products": plan.expected_ice_products,
                        "mineral_needs": plan.mineral_needs,
                        "mineral_delta": plan.mineral_delta,
                        "import_lines": [
                            {"name": n, "quantity": q}
                            for n, q in plan.import_lines()
                        ],
                    },
                    indent=2,
                )
            )
        else:
            self._write_summary(plan, materials, facility, rate_source)

    def _load_materials(self, options) -> Dict[str, int]:
        if options["materials"] and options["from_plan"]:
            raise CommandError("Use only one of --materials or --from-plan")
        if options["materials"]:
            try:
                raw = json.loads(options["materials"])
            except json.JSONDecodeError as exc:
                raise CommandError(f"Invalid --materials JSON: {exc}") from exc
            if not isinstance(raw, dict):
                raise CommandError("--materials must be a JSON object")
            return {str(k): int(v) for k, v in raw.items()}

        if options["from_plan"]:
            me = self._parse_me_te(str(options["me"]), "ME")
            te = self._parse_me_te(str(options["te"]), "TE")
            m_idx, r_idx = self._parse_index_override(
                options["index_override"]
            )
            try:
                build = plan_build(
                    options["from_plan"],
                    quantity=options["quantity"],
                    blueprint_me=me,
                    blueprint_te=te,
                    facility=options["facility"],
                    manufacturing_index=m_idx,
                    reaction_index=r_idx,
                )
            except Exception as exc:
                raise CommandError(str(exc)) from exc
            return {
                name: qty for _, (name, qty) in build.leaf_materials.items()
            }

        raise CommandError("Provide --materials JSON or --from-plan PRODUCT")

    def _parse_me_te(self, value: str, label: str) -> float:
        try:
            raw = float(value)
        except ValueError as exc:
            raise CommandError(f"Invalid {label}: {value!r}") from exc
        if raw < 0:
            raise CommandError(f"{label} must be non-negative")
        return raw / 100.0 if raw > 1.0 else raw

    def _parse_index_override(
        self, value: Optional[str]
    ) -> tuple[Optional[float], Optional[float]]:
        if not value:
            return None, None
        parts = [p.strip() for p in value.split(",")]
        if len(parts) != 2:
            raise CommandError(
                "--index-override must be manufacturing,reaction"
            )
        out = []
        for part in parts:
            raw = float(part)
            out.append(raw / 100.0 if raw > 1.0 else raw)
        return out[0], out[1]

    def _write_summary(
        self,
        plan,
        source_materials: Dict[str, int],
        facility: str,
        rate_source: str,
    ):
        source_note = (
            "override"
            if rate_source == "override"
            else f"{facility} Tatara + Monitor II + skills V"
        )
        tax_note = (
            f", reprocessing_tax={plan.reprocessing_tax:.2%}"
            if plan.includes_compressed_ore
            else " (no compressed ore → no reprocessing tax)"
        )
        self.stdout.write(
            self.style.NOTICE(
                f"Compressed ore plan @ refine_rate={plan.refine_rate:.2%} "
                f"({source_note}){tax_note}"
            )
        )
        self.stdout.write(f"Source leaf lines: {len(source_materials)}")
        _write_moon_ore_section(self.stdout, self.style, plan)
        _write_named_qty_section(
            self.stdout,
            self.style,
            "Compressed belt ore",
            plan.belt_ore_compressed,
        )
        _write_named_qty_section(
            self.stdout,
            self.style,
            "Compressed ice",
            plan.ice_compressed,
        )
        _write_named_qty_section(
            self.stdout,
            self.style,
            "Refined mineral imports",
            plan.mineral_imports,
        )
        for title, bucket in (
            ("PI / other", plan.pi_other_imports),
            ("Ice product imports", plan.ice_imports),
            ("Other", plan.other_imports),
        ):
            _write_named_qty_section(self.stdout, self.style, title, bucket)
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Freighter list"))
        for name, qty in plan.import_lines():
            self.stdout.write(f"  {name}\t{qty:,}")
        _write_mineral_balance_section(self.stdout, self.style, plan)
