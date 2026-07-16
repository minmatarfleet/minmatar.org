"""
Plan a full industry build tree (hull + components + reactions) for Amamake freeports.

Examples:

    pipenv run python manage.py plan_build Typhoon
    pipenv run python manage.py plan_build Typhoon --quantity 1 --me 10 --te 20
    pipenv run python manage.py plan_build 644 --me 0 --format tsv
    pipenv run python manage.py plan_build Typhoon --quantity 10 --compressed

Cost indexes are fetched live from ESI for Amamake unless --index-override is set
(for offline/tests only).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from django.core.management.base import BaseCommand, CommandError

from industry.helpers.build_planner import (
    JobBucket,
    plan_build,
    plan_to_dict,
)
from industry.helpers.compressed_ore import (
    CompressedOrePlan,
    build_compressed_ore_plan,
)
from industry.helpers.facility_profiles import (
    AMAMAKE_SYSTEM_ID,
    FACILITY_PROFILES,
    get_facility_profile,
    get_facility_refine_rate,
    get_facility_reprocessing_tax,
)


def _format_duration(seconds: float) -> str:
    total = int(round(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _parse_me_te(value: str, label: str) -> float:
    """Accept ME/TE as percent (10) or fraction (0.10)."""
    try:
        raw = float(value)
    except ValueError as exc:
        raise CommandError(f"Invalid {label}: {value!r}") from exc
    if raw < 0:
        raise CommandError(f"{label} must be non-negative")
    if raw > 1.0:
        return raw / 100.0
    return raw


def _parse_index_override(
    value: Optional[str],
) -> Tuple[Optional[float], Optional[float]]:
    if not value:
        return None, None
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 2:
        raise CommandError(
            "--index-override must be manufacturing,reaction "
            "(e.g. 0.05,0.04 or 5,4 for percent)"
        )
    out = []
    for part in parts:
        try:
            raw = float(part)
        except ValueError as exc:
            raise CommandError(
                f"Invalid index override value {part!r}"
            ) from exc
        out.append(raw / 100.0 if raw > 1.0 else raw)
    return out[0], out[1]


def _compressed_ore_to_dict(ore_plan: CompressedOrePlan) -> Dict[str, Any]:
    return {
        "refine_rate": ore_plan.refine_rate,
        "reprocessing_tax": ore_plan.reprocessing_tax,
        "includes_compressed_ore": ore_plan.includes_compressed_ore,
        "moon_ore_compressed": ore_plan.moon_ore_compressed,
        "belt_ore_compressed": ore_plan.belt_ore_compressed,
        "moon_mineral_byproducts": ore_plan.moon_mineral_byproducts,
        "mineral_imports": ore_plan.mineral_imports,
        "pi_other_imports": ore_plan.pi_other_imports,
        "ice_imports": ore_plan.ice_imports,
        "other_imports": ore_plan.other_imports,
        "expected_minerals": ore_plan.expected_minerals,
        "mineral_needs": ore_plan.mineral_needs,
        "mineral_delta": ore_plan.mineral_delta,
        "import_lines": [
            {"name": n, "quantity": q} for n, q in ore_plan.import_lines()
        ],
    }


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


def _write_named_qty_lines(
    stdout, bucket: Dict[str, int], *, indent: str = "    "
):
    for name, qty in sorted(bucket.items()):
        stdout.write(f"{indent}{name}\t{qty:,}")


def _write_mineral_balance_lines(
    stdout, ore_plan: CompressedOrePlan, *, indent: str = "    "
):
    names = sorted(
        set(ore_plan.expected_minerals)
        | set(ore_plan.mineral_needs)
        | set(ore_plan.mineral_imports)
    )
    for name in names:
        if name not in _MINERAL_SUMMARY_NAMES:
            continue
        need = ore_plan.mineral_needs.get(name, 0)
        got = ore_plan.expected_minerals.get(name, 0)
        bought = ore_plan.mineral_imports.get(name, 0)
        delta = got + bought - need
        stdout.write(
            f"{indent}{name}\tneed={need:,}\tfrom_ore={got:,}\t"
            f"import={bought:,}\tdelta={delta:+,}"
        )


class Command(BaseCommand):
    help = (
        "Plan manufacture + reaction jobs for a product at Amamake freeports "
        "(Sotiyo + Tatara), with ME/TE-adjusted materials, times, and job costs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "product",
            nargs="?",
            default="Typhoon",
            help="Product name or type id (default: Typhoon).",
        )
        parser.add_argument(
            "--quantity",
            type=int,
            default=1,
            help="Units of the end product to build (default: 1).",
        )
        parser.add_argument(
            "--me",
            default="10",
            help="Blueprint ME as percent (10) or fraction (0.10). Default: 10.",
        )
        parser.add_argument(
            "--te",
            default="20",
            help="Blueprint TE as percent (20) or fraction (0.20). Default: 20.",
        )
        parser.add_argument(
            "--facility",
            default="amamake",
            choices=sorted(FACILITY_PROFILES),
            help="Facility profile key (default: amamake).",
        )
        parser.add_argument(
            "--format",
            choices=("summary", "tsv", "json"),
            default="summary",
            dest="output_format",
            help="Output format (default: summary).",
        )
        parser.add_argument(
            "--index-override",
            default=None,
            help=(
                "Skip ESI and use manufacturing,reaction cost indices "
                "(fractions or percents), e.g. 0.05,0.04"
            ),
        )
        parser.add_argument(
            "--system-id",
            type=int,
            default=None,
            help=(
                "Solar system id for cost indices "
                f"(default: facility profile system, Amamake={AMAMAKE_SYSTEM_ID})."
            ),
        )
        parser.add_argument(
            "--no-fuel-blocks",
            action="store_true",
            help="Treat fuel blocks as imported leaves instead of build jobs.",
        )
        parser.add_argument(
            "--compressed",
            action="store_true",
            help=(
                "Also convert leaf minerals/PI into compressed belt/moon ore "
                "using the facility Tatara refine rate and reprocessing tax."
            ),
        )
        parser.add_argument(
            "--no-moon-ore",
            action="store_true",
            help="With --compressed: do not convert PI P0 into moon ore.",
        )

    def handle(self, *args, **options):
        me = _parse_me_te(str(options["me"]), "ME")
        te = _parse_me_te(str(options["te"]), "TE")
        m_idx, r_idx = _parse_index_override(options["index_override"])

        try:
            plan = plan_build(
                options["product"],
                quantity=options["quantity"],
                blueprint_me=me,
                blueprint_te=te,
                facility=options["facility"],
                manufacturing_index=m_idx,
                reaction_index=r_idx,
                system_id=options["system_id"],
                build_fuel_blocks=not options["no_fuel_blocks"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            if (
                options["index_override"] is None
                and "index" in str(exc).lower()
            ):
                raise CommandError(
                    f"Failed to fetch ESI cost indices ({exc}). "
                    "Pass --index-override manufacturing,reaction for offline use."
                ) from exc
            raise CommandError(str(exc)) from exc

        ore_plan: Optional[CompressedOrePlan] = None
        if options["compressed"]:
            ore_plan = self._build_compressed(
                plan, use_moon_ore=not options["no_moon_ore"]
            )

        fmt = options["output_format"]
        if fmt == "json":
            payload = plan_to_dict(plan)
            if ore_plan is not None:
                payload["compressed_ore"] = _compressed_ore_to_dict(ore_plan)
            self.stdout.write(json.dumps(payload, indent=2))
        elif fmt == "tsv":
            self._write_tsv(plan, ore_plan)
        else:
            self._write_summary(plan, ore_plan)

    def _build_compressed(
        self, plan, *, use_moon_ore: bool
    ) -> CompressedOrePlan:
        materials = {
            name: qty for _, (name, qty) in plan.leaf_materials.items()
        }
        try:
            refine = get_facility_refine_rate(plan.facility_key)
            tax = get_facility_reprocessing_tax(plan.facility_key)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        return build_compressed_ore_plan(
            materials,
            refine_rate=refine,
            use_moon_ore=use_moon_ore,
            reprocessing_tax=tax,
        )

    def _write_summary(
        self, plan, ore_plan: Optional[CompressedOrePlan] = None
    ):
        self.stdout.write(
            self.style.NOTICE(
                f"Build plan: {plan.product_name} x{plan.quantity} "
                f"(ME {plan.blueprint_me * 100:.0f} / TE {plan.blueprint_te * 100:.0f}) "
                f"@ {plan.facility_key}"
            )
        )
        source = "live ESI" if plan.indices_from_esi else "override"
        self.stdout.write(
            f"Cost indices ({source}): manufacturing={plan.manufacturing_index:.6f} "
            f"reaction={plan.reaction_index:.6f} (system {plan.system_id})"
        )
        sample = next(iter(get_facility_profile(plan.facility_key).values()))
        if sample.system_cost_bonus:
            pct = sample.system_cost_bonus * 100
            self.stdout.write(
                f"System cost bonus: {pct:+.0f}% (FW facility pricing; "
                "applies to index gross, not SCC)"
            )
        self.stdout.write("")

        self.stdout.write(self.style.MIGRATE_HEADING("Jobs"))
        bucket_labels = {
            JobBucket.END_PRODUCT: "End products",
            JobBucket.ADVANCED_COMPONENTS: "Advanced components",
            JobBucket.FIRST_STAGE_REACTIONS: "First-stage reactions",
            JobBucket.SECOND_STAGE_REACTIONS: "Second-stage reactions",
            JobBucket.OTHER: "Other",
        }
        by_bucket = plan.jobs_by_bucket()
        durations = plan.bucket_duration_seconds()
        for bucket in JobBucket:
            jobs = by_bucket[bucket]
            if not jobs:
                continue
            self.stdout.write(
                f"  {bucket_labels[bucket]} "
                f"({_format_duration(durations[bucket])}, "
                f"{sum(j.job_cost.total for j in jobs):,} ISK job cost)"
            )
            for job in sorted(jobs, key=lambda j: j.product_name):
                self.stdout.write(
                    f"    - {job.product_name} x{job.runs} runs | "
                    f"{_format_duration(job.duration_seconds)} | "
                    f"{job.job_cost.total:,} ISK | {job.facility_name}"
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING("Leaf materials (buy / import)")
        )
        for _, (name, qty) in sorted(
            plan.leaf_materials.items(), key=lambda x: x[1][0]
        ):
            self.stdout.write(f"  {name}\t{qty:,}")

        if ore_plan is not None:
            self._write_compressed_summary(ore_plan)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Totals"))
        self.stdout.write(
            f"  Sum of job durations: {_format_duration(plan.total_duration_seconds)} "
            f"({plan.total_duration_seconds:,.0f}s) "
            "(parallel slots not applied)"
        )
        self.stdout.write(
            f"  Total installation ISK: {plan.total_job_cost_isk:,}"
        )

    def _write_compressed_summary(self, ore_plan: CompressedOrePlan):
        tax_note = (
            f", reprocessing_tax={ore_plan.reprocessing_tax:.2%}"
            if ore_plan.includes_compressed_ore
            else " (no compressed ore → no reprocessing tax)"
        )
        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Compressed ore @ refine_rate={ore_plan.refine_rate:.2%}"
                f"{tax_note}"
            )
        )
        if ore_plan.moon_ore_compressed:
            self.stdout.write("  Moon ore:")
            _write_named_qty_lines(self.stdout, ore_plan.moon_ore_compressed)
        if ore_plan.belt_ore_compressed:
            self.stdout.write("  Belt ore:")
            _write_named_qty_lines(self.stdout, ore_plan.belt_ore_compressed)
        if ore_plan.mineral_imports:
            self.stdout.write("  Refined mineral imports:")
            _write_named_qty_lines(self.stdout, ore_plan.mineral_imports)
        for title, bucket in (
            ("PI / other", ore_plan.pi_other_imports),
            ("Ice / isotopes", ore_plan.ice_imports),
            ("Other", ore_plan.other_imports),
        ):
            if not bucket:
                continue
            self.stdout.write(f"  {title}:")
            _write_named_qty_lines(self.stdout, bucket)
        self.stdout.write("  Freighter list:")
        for name, qty in ore_plan.import_lines():
            self.stdout.write(f"    {name}\t{qty:,}")
        if ore_plan.expected_minerals:
            self.stdout.write("  Expected refine output (vs leaf needs):")
            _write_mineral_balance_lines(self.stdout, ore_plan)

    def _write_tsv(self, plan, ore_plan: Optional[CompressedOrePlan] = None):
        self.stdout.write(
            "section\tbucket\tproduct\truns\tduration_s\tjob_cost_isk\tfacility"
        )
        for job in plan.jobs:
            self.stdout.write(
                "job\t"
                f"{job.bucket.value}\t{job.product_name}\t{job.runs}\t"
                f"{job.duration_seconds:.2f}\t{job.job_cost.total}\t"
                f"{job.facility_name}"
            )
        for _, (name, qty) in sorted(
            plan.leaf_materials.items(), key=lambda x: x[1][0]
        ):
            self.stdout.write(f"leaf\t\t{name}\t{qty}\t\t\t")
        if ore_plan is not None:
            for name, qty in ore_plan.import_lines():
                self.stdout.write(f"compressed\t\t{name}\t{qty}\t\t\t")
        self.stdout.write(
            f"total\t\t\t\t{plan.total_duration_seconds:.2f}\t"
            f"{plan.total_job_cost_isk}\t"
        )
