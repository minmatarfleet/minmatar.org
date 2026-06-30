"""Sync in-game access lists from the executor character."""

from django.core.management.base import BaseCommand

from access_lists.helpers import (
    DEFAULT_EXECUTOR_CHARACTER_NAME,
    sync_executor_access_lists,
)


class Command(BaseCommand):
    help = (
        "Sync access lists from ESI for the executor character "
        f"(default: {DEFAULT_EXECUTOR_CHARACTER_NAME})."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--character-name",
            type=str,
            default=DEFAULT_EXECUTOR_CHARACTER_NAME,
            help=(
                "Executor character name (partial match). "
                f"Default: {DEFAULT_EXECUTOR_CHARACTER_NAME}."
            ),
        )

    def handle(self, *args, **options):
        character_name = options["character_name"]
        result = sync_executor_access_lists(character_name)

        if not result.get("success"):
            self.stdout.write(
                self.style.ERROR(str(result.get("error", "Sync failed")))
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                "Synced access lists: "
                f"listed={result.get('listed')} "
                f"synced={result.get('synced')} "
                f"removed={result.get('removed')}"
            )
        )
