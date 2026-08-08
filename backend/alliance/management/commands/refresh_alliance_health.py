from django.core.management.base import BaseCommand

from alliance.helpers.health import save_snapshot


class Command(BaseCommand):
    help = "Compute and save an AllianceHealthSnapshot."

    def handle(self, *args, **options):
        snap = save_snapshot()
        self.stdout.write(
            self.style.SUCCESS(
                f"Saved AllianceHealthSnapshot id={snap.id} "
                f"computed_at={snap.computed_at.isoformat()}"
            )
        )
