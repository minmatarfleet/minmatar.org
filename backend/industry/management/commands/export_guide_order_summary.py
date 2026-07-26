"""
Re-run Amamake compressed-ore planner + Jita sell and rewrite the frontend
guide-order-summary data module.

Examples:

    pipenv run python manage.py export_guide_order_summary
    pipenv run python manage.py export_guide_order_summary --dry-run
    pipenv run python manage.py export_guide_order_summary --use-production-lp
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from industry.helpers.guide_order_summary_export import (
    DEFAULT_LP_RATES,
    FACILITY_KEY,
    MIN_ORDER_PROFIT_ISK,
    ORDER_QTY,
    compute_kept_rows,
    default_frontend_module_path,
    write_frontend_module,
)


class Command(BaseCommand):
    help = (
        "Plan guide hulls at Amamake (compressed ore), price finished hulls "
        "at Jita sell, and rewrite frontend guide-order-summary.ts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="",
            help=(
                "Path to write the TypeScript module "
                "(default: frontend/app/src/data/industry/guide-order-summary.ts)."
            ),
        )
        parser.add_argument(
            "--quantity",
            type=int,
            default=ORDER_QTY,
            help=f"Order quantity per hull (default: {ORDER_QTY}).",
        )
        parser.add_argument(
            "--min-order-profit",
            type=int,
            default=MIN_ORDER_PROFIT_ISK,
            help=(
                "Keep lines with x{qty} profit at or above this ISK "
                f"(default: {MIN_ORDER_PROFIT_ISK})."
            ),
        )
        parser.add_argument(
            "--facility",
            default=FACILITY_KEY,
            help=f"Facility key (default: {FACILITY_KEY}).",
        )
        parser.add_argument(
            "--use-production-lp",
            action="store_true",
            help=(
                "Use IndustryLoyaltyPoint catalog defaults instead of the "
                "baked snapshot rates (Minmatar 850 / Caldari 925 / …)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print kept rows without writing the TypeScript module.",
        )

    def handle(self, *args, **options):
        quantity = int(options["quantity"])
        if quantity < 1:
            raise CommandError("--quantity must be >= 1")

        min_profit = int(options["min_order_profit"])
        facility = str(options["facility"]).strip().lower()
        use_production_lp = bool(options["use_production_lp"])
        dry_run = bool(options["dry_run"])

        self.stdout.write(
            f"Planning guide hulls · facility={facility} · qty={quantity} · "
            f"min_x{quantity}={min_profit:,} · "
            f"lp={'production' if use_production_lp else 'snapshot'}…"
        )

        rows = compute_kept_rows(
            quantity=quantity,
            facility=facility,
            min_order_profit=min_profit,
            lp_rates=DEFAULT_LP_RATES,
            use_production_lp=use_production_lp,
        )

        total = sum(r.order_profit for r in rows)
        self.stdout.write(
            f"Kept {len(rows)} hulls · total order profit {total:,}"
        )
        for row in sorted(rows, key=lambda r: -r.order_profit):
            lp = "-" if row.isk_per_lp is None else f"{row.isk_per_lp:g}"
            self.stdout.write(
                f"  {row.name}\tprofit={row.order_profit:,}\t"
                f"cost={row.cost_per:,}\tsell={row.jita_sell:,}\tlp={lp}"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no file written."))
            return

        out = (
            Path(options["output"])
            if options["output"]
            else default_frontend_module_path()
        )
        path = write_frontend_module(
            rows,
            path=out,
            quantity=quantity,
            min_order_profit=min_profit,
            lp_rates=DEFAULT_LP_RATES,
        )
        self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))
