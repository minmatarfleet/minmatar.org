"""Export town hall / member reports for tribe groups."""

import csv
import json
from io import StringIO

from django.core.management.base import BaseCommand, CommandError

from tribes.reports import (
    ReportError,
    all_reportable_groups,
    run_report_by_code,
)
from tribes.reports.runner import run_group_report
from tribes.reports.types import ReportView


class Command(BaseCommand):
    help = "Run tribe group report bindings (town hall / member metrics)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            dest="group_code",
            help="TribeGroup.code (e.g. industry.mining)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Run all non-manual report bindings",
        )
        parser.add_argument(
            "--view",
            default=ReportView.TOWN_HALL.value,
            choices=[v.value for v in ReportView],
        )
        parser.add_argument(
            "--period",
            default="30d",
            help="Period label (e.g. 30d, 12m)",
        )
        parser.add_argument(
            "--format",
            default="json",
            choices=["json", "csv"],
        )

    def handle(self, *args, **options):
        if not options["group_code"] and not options["all"]:
            raise CommandError("Specify --group CODE or --all")

        if options["all"]:
            groups = all_reportable_groups()
            results = []
            for tg in groups:
                try:
                    results.append(
                        run_group_report(
                            tg,
                            view=options["view"],
                            period=options["period"],
                        )
                    )
                except ReportError as exc:
                    self.stderr.write(f"{tg.code}: {exc}")
            payload = [_result_dict(r) for r in results]
            self._emit(payload, options["format"], multi=True)
            return

        try:
            result = run_report_by_code(
                options["group_code"],
                view=options["view"],
                period=options["period"],
            )
        except ReportError as exc:
            raise CommandError(str(exc)) from exc

        if result.manual:
            self.stdout.write(
                json.dumps(_result_dict(result), indent=2, default=str)
            )
            return

        self._emit(_result_dict(result), options["format"], multi=False)

    def _emit(self, payload, fmt, multi):
        if fmt == "json":
            self.stdout.write(json.dumps(payload, indent=2, default=str))
            return

        if multi:
            raise CommandError("CSV output requires a single --group")

        result = payload
        if not result.get("columns"):
            self.stdout.write(json.dumps(result["totals"], indent=2))
            return

        buf = StringIO()
        writer = csv.DictWriter(buf, fieldnames=result["columns"])
        writer.writeheader()
        for row in result["rows"]:
            writer.writerow({k: row.get(k, "") for k in result["columns"]})
        self.stdout.write(buf.getvalue())


def _result_dict(result):
    return {
        "group_id": result.group_id,
        "group_code": result.group_code,
        "group_name": result.group_name,
        "view": result.view,
        "scope": result.scope,
        "period": result.period,
        "period_start": result.period_start.isoformat(),
        "period_end": result.period_end.isoformat(),
        "generated_at": result.generated_at.isoformat(),
        "manual": result.manual,
        "message": result.message,
        "columns": result.columns,
        "rows": result.rows,
        "totals": result.totals,
    }
