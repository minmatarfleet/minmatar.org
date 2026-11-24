"""Create, list and revoke agent keys.

manage.py agent_key create "Claude cloud: Production" [--read-only] [--days 180]
manage.py agent_key list
manage.py agent_key revoke <key prefix>
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from agent_access.keys import create_key
from agent_access.models import AgentKey


class Command(BaseCommand):
    help = "Create, list or revoke the keys agents use for Discord access."

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="action", required=True)
        create = sub.add_parser("create")
        create.add_argument("name")
        create.add_argument("--read-only", action="store_true")
        create.add_argument(
            "--days",
            type=int,
            default=None,
            help="Expire after this many days (default: never).",
        )
        sub.add_parser("list")
        revoke = sub.add_parser("revoke")
        revoke.add_argument("prefix")

    def handle(self, *args, **options):
        action = options["action"]
        if action == "create":
            fields = {"can_write": not options["read_only"]}
            if options["days"]:
                fields["expires_at"] = timezone.now() + timedelta(
                    days=options["days"]
                )
            key, raw = create_key(options["name"], **fields)
            self.stdout.write(f"Created {key}. The key (shown once):")
            self.stdout.write(raw)
        elif action == "list":
            for key in AgentKey.objects.order_by("created_at"):
                state = "active" if key.is_active else "inactive"
                self.stdout.write(
                    f"{key.key_prefix}  {state:8}  "
                    f"{'rw' if key.can_write else 'ro'}  {key.name}  "
                    f"last used {key.last_used_at or 'never'}"
                )
        else:
            keys = AgentKey.objects.filter(
                key_prefix=options["prefix"], revoked_at__isnull=True
            )
            if not keys.exists():
                raise CommandError("No active key with that prefix")
            count = keys.update(revoked_at=timezone.now())
            self.stdout.write(f"Revoked {count} key(s).")
