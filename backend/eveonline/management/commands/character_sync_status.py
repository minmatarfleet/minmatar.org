"""Per-section freshness of character syncs.

Usage:
  python manage.py character_sync_status

Ages are hours since the last successful sync. "Overdue" means older than
twice the section's interval for that character. See
docs/architecture/character-sync.md.
"""

from django.core.management.base import BaseCommand

from eveonline import character_sync


def _hours(value):
    return "-" if value is None else f"{value:.1f}"


class Command(BaseCommand):
    help = "Show per-section character sync freshness."

    def handle(self, *args, **options):
        self.stdout.write(f"Mode: {character_sync.sync_mode()}")
        report = character_sync.freshness_report()
        header = (
            f"{'section':<14}{'in scope':>9}{'overdue':>9}"
            f"{'failing':>9}{'p95 h':>8}{'oldest h':>10}  top errors"
        )
        self.stdout.write(header)
        for name, entry in report["sections"].items():
            errors = ", ".join(f"{e} x{n}" for e, n in entry.top_errors)
            self.stdout.write(
                f"{name:<14}{entry.in_scope:>9}{entry.overdue:>9}"
                f"{entry.failing:>9}{_hours(entry.p95_age_hours):>8}"
                f"{_hours(entry.oldest_age_hours):>10}  {errors}"
            )
        unsynced = report["unsynced_new"]
        self.stdout.write(
            f"New characters with no first fetch: {len(unsynced)}"
            + (f" ({', '.join(map(str, unsynced[:20]))})" if unsynced else "")
        )
