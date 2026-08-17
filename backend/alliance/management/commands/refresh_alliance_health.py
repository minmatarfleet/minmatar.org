from django.core.management.base import BaseCommand

from alliance.helpers.health import latest_snapshot, save_snapshot


class Command(BaseCommand):
    help = "Compute and save an AllianceHealthSnapshot."

    def handle(self, *args, **options):
        previous = latest_snapshot()
        snap = save_snapshot()
        self.stdout.write(
            self.style.SUCCESS(
                f"Saved AllianceHealthSnapshot id={snap.id} "
                f"computed_at={snap.computed_at.isoformat()}"
            )
        )
        prev_roster = None
        if previous:
            prev_roster = (previous.payload or {}).get("roster_people")
        new_roster = (snap.payload or {}).get("roster_people")
        if (
            isinstance(prev_roster, int)
            and isinstance(new_roster, int)
            and prev_roster > 0
            and new_roster < prev_roster // 2
        ):
            self.stdout.write(
                self.style.WARNING(
                    "New snapshot roster_people="
                    f"{new_roster} is far below previous {prev_roster}. "
                    "Local source tables may be incomplete; the dashboard "
                    "reads this latest row. Restore with "
                    "import_alliance_health_from_production --clear."
                )
            )
