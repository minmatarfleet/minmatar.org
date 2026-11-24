"""Create, list and revoke agent keys.

manage.py agent_key create "Claude cloud: Production" [--read-only] [--esi] [--days 180]
manage.py agent_key list
manage.py agent_key revoke <key prefix>
manage.py agent_key esi-grant <key prefix> <character id> [--note ...] [--days 30]
manage.py agent_key esi-revoke <key prefix> <character id>
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from agent_access.keys import create_key
from agent_access.models import AgentEsiCharacter, AgentKey


class Command(BaseCommand):
    help = (
        "Create, list or revoke the keys agents use for Discord and ESI "
        "access, and grant a key ESI access to a character."
    )

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="action", required=True)
        create = sub.add_parser("create")
        create.add_argument("name")
        create.add_argument("--read-only", action="store_true")
        create.add_argument(
            "--esi",
            action="store_true",
            help="May use the ESI endpoint (for characters granted to it).",
        )
        create.add_argument(
            "--days",
            type=int,
            default=None,
            help="Expire after this many days (default: never).",
        )
        sub.add_parser("list")
        revoke = sub.add_parser("revoke")
        revoke.add_argument("prefix")
        grant = sub.add_parser("esi-grant")
        grant.add_argument("prefix")
        grant.add_argument("character_id", type=int)
        grant.add_argument("--note", default="")
        grant.add_argument(
            "--days",
            type=int,
            default=None,
            help="The grant expires after this many days (default: never).",
        )
        ungrant = sub.add_parser("esi-revoke")
        ungrant.add_argument("prefix")
        ungrant.add_argument("character_id", type=int)

    def handle(self, *args, **options):
        action = options["action"]
        if action == "create":
            fields = {
                "can_write": not options["read_only"],
                "can_use_esi": options["esi"],
            }
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
                    f"{'rw' if key.can_write else 'ro'}  "
                    f"{'esi' if key.can_use_esi else '-  '}  {key.name}  "
                    f"last used {key.last_used_at or 'never'}"
                )
        elif action == "esi-grant":
            self._esi_grant(options)
        elif action == "esi-revoke":
            key = self._key(options["prefix"])
            count, _ = AgentEsiCharacter.objects.filter(
                key=key, character_id=options["character_id"]
            ).delete()
            if not count:
                raise CommandError("That key has no grant for that character")
            self.stdout.write("Removed the grant.")
        else:
            keys = AgentKey.objects.filter(
                key_prefix=options["prefix"], revoked_at__isnull=True
            )
            if not keys.exists():
                raise CommandError("No active key with that prefix")
            count = keys.update(revoked_at=timezone.now())
            self.stdout.write(f"Revoked {count} key(s).")

    @staticmethod
    def _key(prefix: str) -> AgentKey:
        key = AgentKey.objects.filter(
            key_prefix=prefix, revoked_at__isnull=True
        ).first()
        if key is None:
            raise CommandError("No active key with that prefix")
        return key

    def _esi_grant(self, options):
        key = self._key(options["prefix"])
        expires_at = None
        if options["days"]:
            expires_at = timezone.now() + timedelta(days=options["days"])
        AgentEsiCharacter.objects.update_or_create(
            key=key,
            character_id=options["character_id"],
            defaults={"note": options["note"], "expires_at": expires_at},
        )
        if not key.can_use_esi:
            key.can_use_esi = True
            key.save(update_fields=["can_use_esi"])
            self.stdout.write(f"Gave {key} ESI access.")
        self.stdout.write(
            f"Granted {key} ESI as character {options['character_id']}"
            + (f" until {expires_at:%Y-%m-%d}" if expires_at else "")
            + "."
        )
