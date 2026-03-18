"""
Fetch corporation roles from ESI and print them (for debugging recruiter/director sync).

Requires a director or CEO of the corporation to have logged in with
esi-corporations.read_corporation_membership.v1.

Usage:
  pipenv run python manage.py corporation_roles_esi 98696436
  pipenv run python manage.py corporation_roles_esi 98696436 --character "C0ach Gar0f"
  pipenv run python manage.py corporation_roles_esi 98696436 --character "C0ach"
"""

from django.core.management.base import BaseCommand

from eveonline.client import EsiClient
from eveonline.helpers.corporations.update import (
    _all_roles_for_member,
    get_director_with_scope,
)
from eveonline.models import EveCorporation

SCOPE_CORPORATION_MEMBERSHIP = [
    "esi-corporations.read_corporation_membership.v1"
]


class Command(BaseCommand):
    help = "Fetch corporation roles from ESI and print (for debugging recruiter sync)."

    def add_arguments(self, parser):
        parser.add_argument(
            "corporation_id",
            type=int,
            help="EVE corporation ID (e.g. 98696436 for Minmatar Fleet Academy).",
        )
        parser.add_argument(
            "--character",
            type=str,
            help="Optional: filter to entries whose character name contains this (case-insensitive).",
        )

    def handle(self, *args, **options):
        corporation_id = options["corporation_id"]
        character_filter = (options.get("character") or "").strip()

        corporation = EveCorporation.objects.filter(
            corporation_id=corporation_id
        ).first()
        if not corporation:
            self.stdout.write(
                self.style.WARNING(
                    f"Corporation {corporation_id} not in DB. Run populate first."
                )
            )
            return

        character = get_director_with_scope(
            corporation, SCOPE_CORPORATION_MEMBERSHIP
        )
        if not character:
            self.stdout.write(
                self.style.ERROR(
                    f"No director/CEO with esi-corporations.read_corporation_membership.v1 "
                    f"for {corporation.name} ({corporation_id}). "
                    "They must log in so we can call ESI."
                )
            )
            return

        self.stdout.write(
            f"Using token for {character.character_name} (character_id={character.character_id})"
        )

        esi_roles = EsiClient(character).get_corporation_roles(corporation_id)
        if not esi_roles.success():
            self.stdout.write(
                self.style.ERROR(
                    f"ESI roles failed: {esi_roles.response_code} {esi_roles.error_text()}"
                )
            )
            return

        roles_data = esi_roles.results() or []
        self.stdout.write(
            f"ESI returned {len(roles_data)} role entries (all pages)."
        )

        if not roles_data:
            self.stdout.write("No role entries.")
            return

        character_ids = [e["character_id"] for e in roles_data]
        try:
            resolved = EsiClient(None).resolve_universe_names(character_ids)
            id_to_name = {r["id"]: r["name"] for r in resolved.results()}
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Resolve names failed: {e}"))
            id_to_name = {}

        for entry in roles_data:
            char_id = entry.get("character_id")
            name = id_to_name.get(char_id, f"<id={char_id}>")
            if (
                character_filter
                and character_filter.lower() not in name.lower()
            ):
                continue
            all_roles = _all_roles_for_member(entry)
            has_personnel_manager = "Personnel_Manager" in all_roles
            self.stdout.write("")
            self.stdout.write(f"  character_id={char_id}  name={name!r}")
            self.stdout.write(f"    roles: {sorted(entry.get('roles') or [])}")
            self.stdout.write(
                f"    roles_at_hq: {sorted(entry.get('roles_at_hq') or [])}"
            )
            self.stdout.write(
                f"    roles_at_base: {sorted(entry.get('roles_at_base') or [])}"
            )
            self.stdout.write(
                f"    roles_at_other: {sorted(entry.get('roles_at_other') or [])}"
            )
            self.stdout.write(
                f"    _all_roles_for_member (used by sync): {sorted(all_roles)}"
            )
            if has_personnel_manager:
                self.stdout.write(
                    self.style.SUCCESS(
                        "    Personnel_Manager in roles? Yes → would be recruiter in app"
                    )
                )
            else:
                self.stdout.write(
                    "    Personnel_Manager in roles? No → would NOT be recruiter in app (need Personnel_Manager)"
                )

        self.stdout.write("")
