"""Load the capability engine's SDE snapshot (what the daily task does)."""

from django.core.management.base import BaseCommand

from capabilities import services
from capabilities.tasks import recompute_everything


class Command(BaseCommand):
    help = (
        "Load an SDE build for the capability engine from a CCP JSONL zip "
        "or unpacked folder (--path), or download the newest one."
    )

    def add_arguments(self, parser):
        parser.add_argument("--path", help="CCP JSONL zip or unpacked folder")
        parser.add_argument(
            "--no-recompute",
            action="store_true",
            help="Only store the snapshot.",
        )

    def handle(self, *args, **options):
        if options["path"]:
            snapshot = services.load_snapshot_from_path(options["path"])
            build = snapshot.build
        else:
            build = services.update_sde_if_new()
            if build is None:
                self.stdout.write("Already on the newest SDE build.")
                return
        self.stdout.write(f"Loaded SDE build {build}.")
        if not options["no_recompute"]:
            self.stdout.write(str(recompute_everything()))
