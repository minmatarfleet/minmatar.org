from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from app.celery import app
from app.queue_health import measure_queues
from app.queue_ops import (
    clear_queued_locks,
    dedupable_task_names,
    dedupe_queued_messages,
)
from app.queues import QUEUES
from app.tasks import broker_client


class Command(BaseCommand):
    help = (
        "Inspect and repair the Celery queues: status, dedupe (dry run "
        "unless --apply), clear-locks. See docs/architecture/celery-queues.md."
    )

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="action", required=True)
        sub.add_parser("status", help="Depth and oldest wait per queue")
        dedupe = sub.add_parser(
            "dedupe",
            help="Drop queued duplicates of the same call (dry run by default)",
        )
        dedupe.add_argument("--apply", action="store_true")
        locks = sub.add_parser(
            "clear-locks",
            help="Forget 'already queued' locks, e.g. after a purge",
        )
        locks.add_argument("--task", help="Only this task name")

    def handle(self, *args, **options):
        action = options["action"]
        if action == "status":
            self._status()
        elif action == "dedupe":
            self._dedupe(options["apply"])
        elif action == "clear-locks":
            try:
                count = clear_queued_locks(options.get("task"))
            except RuntimeError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"Cleared {count} queued lock(s)")

    def _status(self):
        report = measure_queues(broker_client())
        for name, status in report.items():
            spec = QUEUES[name]
            wait = (
                "-"
                if status.oldest_wait is None
                else f"{status.oldest_wait:.0f}s"
            )
            flag = "  BACKED UP" if status.backed_up else ""
            self.stdout.write(
                f"{name:10} {status.depth:7} waiting  oldest {wait:>7} "
                f"(limit {spec.max_wait_seconds}s){flag}"
            )
            for task, count in status.oldest_tasks.most_common(3):
                self.stdout.write(f"{'':10} {count:7} {task}")

    def _dedupe(self, apply: bool):
        app.loader.import_default_modules()
        client = broker_client()
        before = sum(s.depth for s in measure_queues(client).values())
        removed = dedupe_queued_messages(
            client, dedupable_task_names(app.tasks), apply
        )
        for task, count in sorted(removed.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"{count:7} {task}")
        total = sum(removed.values())
        verb = "Removed" if apply else "Would remove (dry run; add --apply)"
        self.stdout.write(f"{verb} {total} duplicate(s) of {before} queued")
