"""Load invention recipes and decryptors from CCP's static data export."""

from django.core.management.base import BaseCommand

from industry.helpers.invention_sde import load_from_path, refresh_if_new


class Command(BaseCommand):
    help = (
        "Load invention outcomes, decryptors and missing blueprints from a "
        "CCP SDE JSONL zip (--path) or download the newest build when ours "
        "is older (--force: even when it is not)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            help="Local CCP SDE JSONL zip or unpacked directory.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reload the newest build even when it is already loaded.",
        )

    def handle(self, *args, **options):
        if options.get("path"):
            build, outcomes, decryptors = load_from_path(options["path"])
            self.stdout.write(
                f"SDE build {build}: {outcomes} outcomes, {decryptors} decryptors"
            )
            return
        build = refresh_if_new(force=options["force"])
        if build is None:
            self.stdout.write("Invention data is already on the newest build.")
        else:
            self.stdout.write(f"Loaded invention data from SDE build {build}.")
